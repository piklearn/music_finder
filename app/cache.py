"""Tiny SQLite-backed page cache, so repeated songs don't re-hit every site."""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path


class Cache:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS cache ("
                " url TEXT PRIMARY KEY,"
                " body TEXT NOT NULL,"
                " content_type TEXT,"
                " final_url TEXT,"
                " fetched_at REAL NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def get(self, url: str, ttl: float) -> dict | None:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT body, content_type, final_url, fetched_at FROM cache WHERE url=?",
                    (url,),
                ).fetchone()
            finally:
                conn.close()
        if not row:
            return None
        body, content_type, final_url, fetched_at = row
        if ttl and time.time() - fetched_at > ttl:
            return None
        return {"body": body, "content_type": content_type, "final_url": final_url}

    def set(self, url: str, body: str, content_type: str, final_url: str) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO cache (url, body, content_type, final_url, fetched_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (url, body, content_type, final_url, time.time()),
                )
                conn.commit()
            finally:
                conn.close()

    def clear(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM cache")
                conn.commit()
            finally:
                conn.close()
