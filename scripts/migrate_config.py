#!/usr/bin/env python3
"""Merge missing keys from config.example.toml into config.toml."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from app.config.settings import _dump_toml


def merge(base: dict, incoming: dict) -> dict:
    out = dict(base)
    for key, value in incoming.items():
        if key not in out:
            out[key] = value
        elif isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge(out[key], value)
    return out


def main() -> int:
    example = ROOT / "config.example.toml"
    target = ROOT / "config.toml"
    if not example.exists():
        print("config.example.toml missing")
        return 1
    with example.open("rb") as handle:
        src = tomllib.load(handle)
    current = {}
    if target.exists():
        with target.open("rb") as handle:
            current = tomllib.load(handle)
    merged = merge(src, current)
    # keep user values: merge(example, current) would overwrite with current
    merged = merge(src, current)
    target.write_text(_dump_toml(merged), encoding="utf-8")
    print(f"Updated {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
