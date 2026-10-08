"""In-process progress bus used by the API, CLI, and WebUI."""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from collections.abc import Callable
from typing import Any


ProgressCallback = Callable[[int, str, dict], None]


class ProgressBus:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._state: dict[str, dict[str, Any]] = {}
        self._listeners: dict[str, list[ProgressCallback]] = defaultdict(list)

    def snapshot(self, task_id: str) -> dict[str, Any]:
        with self._lock:
            return dict(self._state.get(task_id) or {"progress": 0, "stage": "queued"})

    def update(self, task_id: str, progress: int, stage: str, **extra: Any) -> dict[str, Any]:
        payload = {
            "task_id": task_id,
            "progress": max(0, min(100, int(progress))),
            "stage": stage,
            "updated_at": time.time(),
            **extra,
        }
        with self._lock:
            current = self._state.get(task_id, {})
            current.update(payload)
            self._state[task_id] = current
            listeners = list(self._listeners.get(task_id, []))
            snapshot = dict(current)
        for cb in listeners:
            try:
                cb(snapshot["progress"], stage, snapshot)
            except Exception:
                pass
        return snapshot

    def subscribe(self, task_id: str, callback: ProgressCallback) -> None:
        with self._lock:
            self._listeners[task_id].append(callback)

    def unsubscribe(self, task_id: str, callback: ProgressCallback) -> None:
        with self._lock:
            listeners = self._listeners.get(task_id, [])
            if callback in listeners:
                listeners.remove(callback)

    def drop(self, task_id: str) -> None:
        with self._lock:
            self._state.pop(task_id, None)
            self._listeners.pop(task_id, None)


bus = ProgressBus()
