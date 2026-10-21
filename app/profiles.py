"""YAML-backed store of site profiles (edited from the UI)."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import yaml

from .models import SiteProfile

_HEADER = """# Music Finder site profiles.
# Each entry is a reusable recipe: search URL + CSS selectors.
# Edit this file by hand or from the web UI.

"""

_EMPTY = _HEADER + "sites: []\n"


class SiteStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        if not self.path.exists():
            self.path.write_text(_EMPTY, encoding="utf-8")

    def _read(self) -> list[SiteProfile]:
        try:
            raw = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise ValueError(f"sites.yaml معتبر نیست: {exc}") from exc
        items = raw.get("sites") if isinstance(raw, dict) else raw
        profiles: list[SiteProfile] = []
        for item in items or []:
            try:
                profiles.append(SiteProfile(**item))
            except Exception:
                # skip malformed entries instead of breaking the whole app
                continue
        return profiles

    def _write(self, profiles: list[SiteProfile]) -> None:
        data = {"sites": [p.model_dump() for p in profiles]}
        self.path.write_text(_HEADER + yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def list(self) -> list[SiteProfile]:
        with self._lock:
            return self._read()

    def get(self, site_id: str) -> SiteProfile | None:
        return next((p for p in self.list() if p.id == site_id), None)

    def upsert(self, profile: SiteProfile) -> SiteProfile:
        with self._lock:
            profiles = self._read()
            for i, existing in enumerate(profiles):
                if existing.id == profile.id:
                    profiles[i] = profile
                    break
            else:
                profiles.append(profile)
            self._write(profiles)
        return profile

    def delete(self, site_id: str) -> bool:
        with self._lock:
            profiles = self._read()
            kept = [p for p in profiles if p.id != site_id]
            if len(kept) == len(profiles):
                return False
            self._write(kept)
        return True

    def replace(self, profiles: list[SiteProfile]) -> None:
        with self._lock:
            self._write(profiles)


def parse_profiles(content: str) -> tuple[list[SiteProfile], list[str]]:
    """Parse an exported YAML/JSON config into profiles + a list of problems."""
    text = (content or "").strip()
    if not text:
        return [], ["فایل خالی است"]

    data = None
    errors: list[str] = []
    try:
        if text.startswith("{") or text.startswith("["):
            data = json.loads(text)
        else:
            data = yaml.safe_load(text)
    except json.JSONDecodeError as exc:
        return [], [f"JSON نامعتبر: {exc}"]
    except yaml.YAMLError as exc:
        return [], [f"YAML نامعتبر: {exc}"]

    if isinstance(data, dict):
        items = data.get("sites", data.get("profiles", []))
    elif isinstance(data, list):
        items = data
    else:
        return [], ["ساختار فایل شناسایی نشد (انتظار: کلید sites یا یک لیست)"]

    if not isinstance(items, list):
        return [], ["مقدار sites باید یک لیست باشد"]

    profiles: list[SiteProfile] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(f"مورد {index}: یک شیء نیست")
            continue
        try:
            profiles.append(SiteProfile(**item))
        except Exception as exc:
            label = item.get("id", f"مورد {index}")
            errors.append(f"{label}: {exc}")

    return profiles, errors
