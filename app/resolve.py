"""Two-stage resolution: search page -> result items -> detail page -> download link."""

from __future__ import annotations

import asyncio
import re
from urllib.parse import quote_plus, urljoin, urlsplit, urlunsplit

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from . import normalize
from .fetcher import FetchError, Fetcher, RobotsDenied
from .models import SiteProfile
from .verify import AUDIO_EXT_RE, verify_link

DOWNLOAD_HINT = re.compile(
    r"(download|dl\.|/dl/|/get/|دانلود|\.mp3|\.m4a|\.flac|\.ogg|\.wav|\.aac)", re.I
)
_JUNK_HREF = re.compile(r"^(#|javascript:|mailto:|tel:)", re.I)


def _text(node) -> str:
    if node is None:
        return ""
    return re.sub(r"\s+", " ", node.text(separator=" ")).strip()


def _href(node) -> str:
    if node is None:
        return ""
    return (node.attributes or {}).get("href", "").strip()


def _absolute(base: str, href: str) -> str:
    if not href or _JUNK_HREF.search(href):
        return ""
    return urljoin(base, href)


def _same_page(a: str, b: str) -> bool:
    def clean(u: str) -> str:
        s = urlsplit(u)
        return urlunsplit((s.scheme, s.netloc, s.path.rstrip("/"), s.query, ""))

    return clean(a) == clean(b)


def parse_results(html: str, profile: SiteProfile, page_url: str) -> list[dict]:
    """Extract candidate rows from a search results page with the profile's selectors."""
    if not profile.result_selector:
        return []
    tree = HTMLParser(html)
    base = profile.base or page_url
    items: list[dict] = []
    seen: set[str] = set()

    for node in tree.css(profile.result_selector):
        title_node = node.css_first(profile.title_selector) if profile.title_selector else node
        link_node = node.css_first(profile.detail_link_selector) if profile.detail_link_selector else title_node

        title = _text(title_node) or _text(link_node)
        artist = _text(node.css_first(profile.artist_selector)) if profile.artist_selector else ""
        detail = _absolute(base, _href(link_node) or _href(title_node))
        if not title:
            continue

        key = detail or title
        if key in seen:
            continue
        seen.add(key)

        item = {
            "title": title,
            "artist": artist,
            "detail_url": detail,
            "download_url": "",
            "link_kind": "",
            "candidates": [],
        }

        if profile.download_on == "result" and profile.download_selector:
            download_node = node.css_first(profile.download_selector)
            download_url = _absolute(base, _href(download_node) or _href(download_node.css_first("a") if download_node else None))
            if download_url:
                item["download_url"] = download_url
                item["link_kind"] = "direct" if AUDIO_EXT_RE.search(urlsplit(download_url).path) else "page"
        items.append(item)

    return items


def find_download_links(html: str, page_url: str, profile: SiteProfile | None = None) -> list[dict]:
    """Collect and score download-link candidates on a song page.

    Priority: explicit selector from the profile, then <audio>/<source>, then
    keyword/extension heuristics. Nothing is downloaded here.
    """
    tree = HTMLParser(html)
    found: dict[str, dict] = {}

    def add(href: str, label: str, score: int, origin: str) -> None:
        url = _absolute(page_url, href)
        if not url or _same_page(url, page_url):
            return
        is_audio = bool(AUDIO_EXT_RE.search(urlsplit(url).path))
        kind = "direct" if is_audio else "page"
        if is_audio:
            score += 40
        if DOWNLOAD_HINT.search(url):
            score += 25
        if DOWNLOAD_HINT.search(label or ""):
            score += 20
        current = found.get(url)
        if current is None or current["score"] < score:
            found[url] = {"url": url, "label": label.strip(), "kind": kind, "score": score, "origin": origin}

    if profile is not None and profile.download_selector:
        for node in tree.css(profile.download_selector):
            anchor = node if node.tag == "a" else node.css_first("a")
            add(_href(anchor), _text(anchor) or _text(node), 200, "selector")
        # a selector may point at a wrapper that holds the real link
        if not found:
            for node in tree.css(profile.download_selector):
                add(_href(node), _text(node), 150, "selector")

    for node in tree.css("audio[src]"):
        add(node.attributes.get("src", ""), "audio", 150, "audio-tag")
    for node in tree.css("audio source[src]"):
        add(node.attributes.get("src", ""), "audio", 150, "audio-tag")
    for node in tree.css("video source[src]"):
        add(node.attributes.get("src", ""), "video", 120, "video-tag")

    for node in tree.css("a[href]"):
        href = _href(node)
        label = _text(node)
        if DOWNLOAD_HINT.search(href) or DOWNLOAD_HINT.search(label):
            add(href, label, 50, "heuristic")
        elif AUDIO_EXT_RE.search(urlsplit(urljoin(page_url, href)).path):
            add(href, label, 60, "extension")

    return sorted(found.values(), key=lambda c: c["score"], reverse=True)


def build_search_url(profile: SiteProfile, query: str) -> str:
    if "{query}" not in profile.search_url:
        raise ValueError(f"search_url سایت «{profile.name or profile.id}» باید شامل {{query}} باشد")
    return profile.search_url.replace("{query}", quote_plus(query.strip()))


async def resolve_site(
    fetcher: Fetcher,
    profile: SiteProfile,
    query: str,
    *,
    limit: int = 4,
    verify_links: bool = True,
    encoding: str = "",
) -> dict:
    """Run the full recipe for one site and one query."""
    result: dict = {
        "site_id": profile.id,
        "site_name": profile.name or profile.id,
        "results": [],
        "error": "",
    }
    try:
        search_url = build_search_url(profile, query)
        html, final_url = await fetcher.get_text(search_url, encoding=encoding or profile.charset)
        items = parse_results(html, profile, final_url)
    except RobotsDenied as exc:
        result["error"] = str(exc)
        return result
    except (FetchError, ValueError) as exc:
        result["error"] = str(exc)
        return result
    except Exception as exc:  # selector/parse problems should not kill the whole search
        result["error"] = f"خطا در خواندن صفحهٔ نتایج: {exc}"
        return result

    for item in items:
        item["score"] = round(normalize.score(query, item["title"], item["artist"]), 3)

    items.sort(key=lambda i: i["score"], reverse=True)
    items = items[: max(1, limit)]

    semaphore = asyncio.Semaphore(3)

    async def enrich(item: dict) -> dict:
        async with semaphore:
            if not item.get("download_url") and item.get("detail_url"):
                try:
                    detail_html, detail_final = await fetcher.get_text(
                        item["detail_url"], encoding=encoding or profile.charset
                    )
                    candidates = find_download_links(detail_html, detail_final, profile)
                    item["candidates"] = candidates[:5]
                    if candidates:
                        item["download_url"] = candidates[0]["url"]
                        item["link_kind"] = candidates[0]["kind"]
                except RobotsDenied as exc:
                    item["note"] = str(exc)
                except FetchError as exc:
                    item["note"] = f"صفحهٔ آهنگ باز نشد: {exc}"
                except Exception as exc:
                    item["note"] = f"خطا در استخراج لینک: {exc}"

            if verify_links and item.get("download_url"):
                item["verified"] = await verify_link(fetcher.client, item["download_url"])
                if item["verified"] and item["verified"].get("direct"):
                    item["link_kind"] = "direct"
            return item

    result["results"] = list(await asyncio.gather(*(enrich(i) for i in items)))
    return result


async def resolve_many(
    fetcher: Fetcher,
    profiles: list[SiteProfile],
    query: str,
    *,
    limit: int = 4,
    verify_links: bool = True,
) -> list[dict]:
    return list(
        await asyncio.gather(
            *(resolve_site(fetcher, p, query, limit=limit, verify_links=verify_links) for p in profiles)
        )
    )
