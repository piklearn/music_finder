"""Lyrics -> song identification using LRCLIB (free, no API key)."""

from __future__ import annotations

import httpx

from . import normalize

LRCLIB_SEARCH = "https://lrclib.net/api/search"


def _lyrics_match(query: str, lyrics: str) -> float:
    if not lyrics:
        return 0.0
    q_tokens = normalize.tokens(query)
    if not q_tokens:
        return 0.0
    lyrics_norm = normalize.normalize(lyrics)
    lyrics_tokens = set(lyrics_norm.split())
    coverage = sum(1 for t in q_tokens if t in lyrics_tokens) / len(q_tokens)
    phrase = 1.0 if normalize.normalize(query) in lyrics_norm else 0.0
    return round(0.7 * coverage + 0.3 * phrase, 3)


async def guess_songs(client: httpx.AsyncClient, query: str, limit: int = 5) -> list[dict]:
    """Return possible (title, artist) pairs for a lyrics snippet."""
    try:
        resp = await client.get(
            LRCLIB_SEARCH,
            params={"q": query},
            headers={"User-Agent": "MusicFinder/0.1 (local personal use)"},
            timeout=20,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return []

    if not isinstance(data, list):
        return []

    guesses = []
    for item in data[:25]:
        if not isinstance(item, dict):
            continue
        title = item.get("trackName") or ""
        artist = item.get("artistName") or ""
        if not title:
            continue
        lyrics = item.get("plainLyrics") or item.get("syncedLyrics") or ""
        guesses.append(
            {
                "title": title,
                "artist": artist,
                "album": item.get("albumName") or "",
                "duration": item.get("duration"),
                "lyrics_match": _lyrics_match(query, lyrics),
            }
        )

    guesses.sort(key=lambda g: (g["lyrics_match"], len(g["title"])), reverse=True)
    return guesses[:limit]
