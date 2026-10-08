"""Environment helpers. Values in .env and the process env override TOML."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_LOADED = False


def load_env(root: Path | None = None) -> None:
    global _LOADED
    if _LOADED:
        return
    base = root or Path(__file__).resolve().parents[2]
    load_dotenv(base / ".env", override=False)
    _LOADED = True


def env(key: str, default: str | None = None) -> str | None:
    load_env()
    value = os.environ.get(key)
    if value is None or value == "":
        return default
    return value


def env_bool(key: str, default: bool = False) -> bool:
    raw = env(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def first_env(*keys: str, default: str | None = None) -> str | None:
    for key in keys:
        value = env(key)
        if value:
            return value
    return default
