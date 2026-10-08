#!/usr/bin/env python3
"""Create .env, master key, encrypted DB, and the first admin."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.security.bootstrap import bootstrap
from app.security.crypto import ensure_master_key
from app.utils.file_manager import ROOT as APP_ROOT


def main() -> int:
    example = APP_ROOT / ".env.example"
    target = APP_ROOT / ".env"
    if not target.exists() and example.exists():
        shutil.copy(example, target)
        print("created .env from .env.example")
    ensure_master_key(APP_ROOT)
    info = bootstrap(APP_ROOT)
    print(f"admin user : {info['admin']}")
    print(f"created    : {info['created']}")
    if info.get("vault_recovered"):
        print("vault      : old database could not be unlocked — started a fresh one")
        print("             (previous file saved as data/framegenius.db.enc.broken-*)")
    note = APP_ROOT / "data" / "FIRST_LOGIN.txt"
    if note.exists():
        print(f"credentials: {note}")
    print("encrypted db: data/framegenius.db.enc")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
