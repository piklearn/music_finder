"""Polite HTTP layer: per-host throttling, robots.txt, page cache."""

from __future__ import annotations

import asyncio
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from .cache import Cache

USER_AGENT = "MusicFinder/0.1 (local personal use)"


class RobotsDenied(Exception):
    pass


class FetchError(Exception):
    pass


class Fetcher:
    def __init__(
        self,
        cache: Cache | None = None,
        *,
        timeout: float = 25.0,
        min_interval: float = 1.0,
        respect_robots: bool = True,
        cache_ttl: float = 1800.0,
    ):
        self.cache = cache
        self.cache_ttl = cache_ttl
        self.min_interval = min_interval
        self.respect_robots = respect_robots
        self._last_request: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._robots: dict[str, RobotFileParser | None] = {}
        self._robots_locks: dict[str, asyncio.Lock] = {}
        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
                "Accept-Language": "fa,en;q=0.8",
            },
            timeout=timeout,
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        await self.client.aclose()

    # ---------------------------------------------------------------- internals
    async def _throttle(self, host: str) -> None:
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            now = time.monotonic()
            last = self._last_request.get(host, 0.0)
            wait = self.min_interval - (now - last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request[host] = time.monotonic()

    async def _robots_for(self, url: str) -> RobotFileParser | None:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin in self._robots:
            return self._robots[origin]

        lock = self._robots_locks.setdefault(origin, asyncio.Lock())
        async with lock:
            if origin in self._robots:
                return self._robots[origin]
            parser: RobotFileParser | None = None
            try:
                resp = await self.client.get(f"{origin}/robots.txt", timeout=10)
                if resp.status_code == 200:
                    parser = RobotFileParser()
                    parser.parse(resp.text.splitlines())
                elif resp.status_code in (401, 403):
                    parser = RobotFileParser()
                    parser.disallow_all = True
            except Exception:
                parser = None
            self._robots[origin] = parser
            return parser

    async def _check_robots(self, url: str) -> None:
        if not self.respect_robots:
            return
        parser = await self._robots_for(url)
        if parser is not None and not parser.can_fetch(USER_AGENT, url):
            raise RobotsDenied(f"robots.txt اجازه نمی‌دهد: {url}")

    async def get(self, url: str, *, encoding: str = "") -> httpx.Response:
        """Uncached GET (used for verification / robots probing)."""
        host = urlparse(url).netloc
        await self._throttle(host)
        try:
            return await self.client.get(url)
        except httpx.HTTPError as exc:
            raise FetchError(str(exc)) from exc

    async def head(self, url: str) -> httpx.Response:
        host = urlparse(url).netloc
        await self._throttle(host)
        try:
            return await self.client.head(url)
        except httpx.HTTPError as exc:
            raise FetchError(str(exc)) from exc

    async def get_text(self, url: str, *, encoding: str = "", use_cache: bool = True) -> tuple[str, str]:
        """Return (html, final_url). Cached on the requested URL."""
        if use_cache and self.cache is not None:
            hit = self.cache.get(url, self.cache_ttl)
            if hit is not None:
                return hit["body"], hit["final_url"] or url

        await self._check_robots(url)
        resp = await self.get(url)
        if resp.status_code >= 400:
            raise FetchError(f"HTTP {resp.status_code} برای {url}")

        if encoding:
            body = resp.content.decode(encoding, errors="replace")
        else:
            body = resp.text
        final_url = str(resp.url)

        if use_cache and self.cache is not None:
            self.cache.set(url, body, resp.headers.get("content-type", ""), final_url)
        return body, final_url
