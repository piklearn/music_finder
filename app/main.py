from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import lyrics
from .cache import Cache
from .fetcher import Fetcher, FetchError, RobotsDenied
from .history import History
from .infer import infer_all
from .models import InferRequest, SearchRequest, SiteProfile, TestRequest
from .profiles import SiteStore
from .resolve import resolve_site

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

cache = Cache(DATA_DIR / "cache.sqlite")
history = History(DATA_DIR / "history.sqlite")
store = SiteStore(BASE_DIR / "sites.yaml")

fetcher: Fetcher | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global fetcher
    fetcher = Fetcher(cache=cache)
    try:
        yield
    finally:
        await fetcher.aclose()
        fetcher = None


app = FastAPI(title="Music Finder", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def get_fetcher() -> Fetcher:
    if fetcher is None:  # pragma: no cover - only outside the app lifespan
        raise HTTPException(status_code=503, detail="سرویس واکشی آماده نیست")
    return fetcher


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(TEMPLATES_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "sites": len(store.list())}


# --------------------------------------------------------------------- sites
@app.get("/api/sites")
async def list_sites() -> dict:
    return {"sites": [p.model_dump() for p in store.list()]}


@app.post("/api/sites")
async def save_site(profile: SiteProfile) -> dict:
    if not profile.name:
        profile.name = profile.id
    if not profile.base:
        profile.base = ""
    store.upsert(profile)
    return {"ok": True, "site": profile.model_dump()}


@app.delete("/api/sites/{site_id}")
async def delete_site(site_id: str) -> dict:
    if not store.delete(site_id):
        raise HTTPException(status_code=404, detail="سایت پیدا نشد")
    return {"ok": True}


@app.post("/api/sites/infer")
async def infer_site(payload: InferRequest) -> dict:
    try:
        suggestion = await infer_all(
            get_fetcher(), payload.search_url, payload.detail_url, payload.query_hint
        )
    except RobotsDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except FetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"استنباط ناموفق بود: {exc}") from exc
    return suggestion


@app.post("/api/sites/{site_id}/test")
async def test_site(site_id: str, payload: TestRequest) -> dict:
    profile = store.get(site_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="سایت پیدا نشد")
    return await resolve_site(
        get_fetcher(), profile, payload.query, limit=3, verify_links=payload.verify
    )


# -------------------------------------------------------------------- search
def _canonical(url: str) -> str:
    return url.split("#")[0].rstrip("/")


def _dedupe(results: list[dict]) -> list[dict]:
    best: dict[str, dict] = {}
    for item in results:
        key = item.get("download_url") or item.get("detail_url") or f"{item['site_id']}:{item['title']}"
        key = _canonical(key)
        if key not in best or best[key]["score"] < item["score"]:
            best[key] = item
    return sorted(best.values(), key=lambda i: i["score"], reverse=True)


@app.post("/api/search")
async def search(payload: SearchRequest) -> dict:
    sites = [p for p in store.list() if p.enabled and (not payload.site_ids or p.id in payload.site_ids)]
    if not sites:
        raise HTTPException(
            status_code=400,
            detail="هیچ سایتی انتخاب نشده. اول در تب «سایت‌ها» یک سایت اضافه کن.",
        )

    guesses: list[dict] = []
    queries: list[str] = [payload.query.strip()]

    if payload.mode == "lyrics":
        guesses = await lyrics.guess_songs(get_fetcher().client, payload.query)
        if guesses:
            queries = []
            for guess in guesses[:2]:
                label = f"{guess['artist']} {guess['title']}".strip()
                if label and label not in queries:
                    queries.append(label)
        # if nothing was identified we still search the raw snippet

    per_site_runs = await _gather_runs(sites, queries, payload.limit_per_site, payload.verify)

    merged: list[dict] = []
    errors: dict[str, str] = {}
    for run in per_site_runs:
        if run["error"]:
            errors[run["site_id"]] = run["error"]
            continue
        for item in run["results"]:
            item["site_id"] = run["site_id"]
            item["site_name"] = run["site_name"]
            merged.append(item)

    results = _dedupe(merged)
    history.add(payload.query, payload.mode, len(results))

    return {
        "query": payload.query,
        "mode": payload.mode,
        "searched_queries": queries,
        "guesses": guesses,
        "results": results,
        "errors": [{"site_id": k, "message": v} for k, v in errors.items()],
        "count": len(results),
    }


async def _gather_runs(sites, queries, limit, verify):
    import asyncio

    tasks = [
        resolve_site(get_fetcher(), site, query, limit=limit, verify_links=verify)
        for query in queries
        for site in sites
    ]
    return list(await asyncio.gather(*tasks))


# ------------------------------------------------------------------- history
@app.get("/api/history")
async def get_history(limit: int = 20) -> dict:
    return {"history": history.list(max(1, min(limit, 100)))}


@app.delete("/api/history")
async def clear_history() -> dict:
    history.clear()
    return {"ok": True}


@app.post("/api/cache/clear")
async def clear_cache() -> dict:
    cache.clear()
    return {"ok": True}
