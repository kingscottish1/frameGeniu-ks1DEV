"""Tiny JSON disk cache for provider responses and media lookups."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any


class DiskCache:
    def __init__(self, folder: Path, ttl: int = 3600) -> None:
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.folder / f"{digest}.json"

    def get(self, key: str) -> Any | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if time.time() - payload.get("ts", 0) > self.ttl:
            path.unlink(missing_ok=True)
            return None
        return payload.get("value")

    def set(self, key: str, value: Any) -> None:
        path = self._path(key)
        path.write_text(json.dumps({"ts": time.time(), "value": value}, ensure_ascii=False), encoding="utf-8")

    def clear(self) -> None:
        for item in self.folder.glob("*.json"):
            item.unlink(missing_ok=True)
