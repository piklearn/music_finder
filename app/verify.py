"""Validate a download link without downloading the file: HEAD, then ranged GET."""

from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx

AUDIO_EXT_RE = re.compile(r"\.(mp3|m4a|flac|ogg|opus|wav|aac|m4b|mp4)(?:$|[?#])", re.I)
AUDIO_TYPES = ("audio/", "application/ogg", "application/octet-stream", "binary/octet-stream")


def is_audio_url(url: str) -> bool:
    return bool(AUDIO_EXT_RE.search(urlparse(url).path))


async def verify_link(client: httpx.AsyncClient, url: str) -> dict | None:
    """Return {ok, status, content_type, size, final_url, direct} or None on failure."""
    info: dict = {
        "ok": False,
        "status": None,
        "content_type": "",
        "size": None,
        "final_url": url,
        "direct": is_audio_url(url),
    }
    try:
        resp = await client.head(url)
        if resp.status_code in (403, 405, 501) or not resp.headers.get("content-type"):
            resp = await client.get(url, headers={"Range": "bytes=0-0"})
    except httpx.HTTPError:
        return None

    info["status"] = resp.status_code
    info["final_url"] = str(resp.url)
    content_type = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
    info["content_type"] = content_type
    info["ok"] = resp.status_code < 400

    length = resp.headers.get("content-length")
    if length and length.isdigit():
        size = int(length)
        if "range" in (resp.headers.get("content-range") or "").lower():
            total = resp.headers.get("content-range", "").split("/")[-1]
            if total.isdigit():
                size = int(total)
        info["size"] = size

    if any(content_type.startswith(t) for t in AUDIO_TYPES) or is_audio_url(info["final_url"]):
        info["direct"] = True
    return info
