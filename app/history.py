"""Search history, kept in the same SQLite file family as the cache."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path


class History:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS history ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " query TEXT NOT NULL,"
                " mode TEXT NOT NULL,"
                " result_count INTEGER DEFAULT 0,"
                " created_at TEXT NOT NULL DEFAULT (datetime('now')))"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=5)

    def add(self, query: str, mode: str, result_count: int) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO history (query, mode, result_count) VALUES (?, ?, ?)",
                    (query, mode, result_count),
                )
                conn.commit()
            finally:
                conn.close()

    def list(self, limit: int = 20) -> list[dict]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT id, query, mode, result_count, created_at FROM history"
                    " ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            finally:
                conn.close()
        return [
            {"id": r[0], "query": r[1], "mode": r[2], "result_count": r[3], "created_at": r[4]}
            for r in rows
        ]

    def clear(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM history")
                conn.commit()
            finally:
                conn.close()
