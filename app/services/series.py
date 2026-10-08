"""Series continuity for ANY subject the user types. Nothing is hardcoded."""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.config.settings import get_settings
from app.utils.logger import get_logger

log = get_logger("series")


def series_label(name: str, part: int | None = None, total: int | None = None) -> str:
    name = (name or "").strip()
    if not name:
        return ""
    if part and total:
        return f"{name} · Part {int(part)} of {int(total)}"
    if part:
        return f"{name} · Part {int(part)}"
    return name


def recap_line(topic: str, name: str, part: int, previous_hook: str = "") -> str:
    if previous_hook:
        return f"Last time on {name}. {previous_hook.rstrip('.')}."
    if part > 1:
        return f"Last time on {name} we opened {topic}. Tonight we go further."
    return f"This is {name}. Part one of the story of {topic}."


def tease_line(topic: str, name: str, part: int, total: int | None) -> str:
    nxt = int(part or 1) + 1
    if total and nxt > int(total):
        return "Sub and follow."
    if total:
        return f"Sub and follow for part {nxt}."
    return "Sub and follow."


def _store() -> Path:
    path = get_settings().files.output_dir / "series.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower()) or "series"


def remember(name: str, part: int, total: int | None, hook: str, topic: str) -> None:
    path = _store()
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data[_key(name)] = {
        "name": name,
        "part": int(part or 1),
        "total": int(total) if total else None,
        "hook": (hook or "")[:180],
        "topic": topic,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def recall(name: str) -> dict:
    path = _store()
    if not path.exists() or not name:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data.get(_key(name)) or {}


def suggest_next(name: str) -> int:
    prev = recall(name)
    return int(prev.get("part") or 0) + 1
