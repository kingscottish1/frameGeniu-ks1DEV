#!/usr/bin/env python3
"""Create the local account, save it to .env + ACCOUNT.txt, and open the studio gate."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.security.bootstrap import DEFAULT_ADMIN_PASSWORD, bootstrap
from app.security.crypto import hash_password, upsert_env, _chmod_private
from app.security.db import data_folder, get_db
from app.utils.env import load_env

USER = "admin"
PASSWORD = DEFAULT_ADMIN_PASSWORD


def write_account_file() -> Path:
    text = (
        "FrameGenius account — copy these, change later in Vault if you turn auth on.\n"
        "\n"
        f"  Operator     {USER}\n"
        f"  Passphrase   {PASSWORD}\n"
        "\n"
        "Login gate is OFF (same as MoneyPrinterTurbo). The studio opens by itself.\n"
        "To lock it later set FRAMEGENIUS_AUTH=1 in .env and restart.\n"
    )
    path = ROOT / "ACCOUNT.txt"
    path.write_text(text, encoding="utf-8")
    note = data_folder() / "FIRST_LOGIN.txt"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(f"user: {USER}\npass: {PASSWORD}\n", encoding="utf-8")
    _chmod_private(note)
    return path


def main() -> int:
    load_env(ROOT)
    upsert_env(ROOT / ".env", "FRAMEGENIUS_ADMIN_USER", USER)
    upsert_env(ROOT / ".env", "FRAMEGENIUS_ADMIN_PASSWORD", PASSWORD)
    upsert_env(ROOT / ".env", "FRAMEGENIUS_AUTH", "0")
    upsert_env(ROOT / ".env", "FRAMEGENIUS_LLM_PROVIDER", "auto")
    upsert_env(ROOT / ".env", "FRAMEGENIUS_RESET_ADMIN", "1")
    bootstrap(ROOT)
    db = get_db()
    row = db.one("SELECT id FROM users WHERE username=?", (USER,))
    if row:
        db.execute(
            "UPDATE users SET password_hash=?, failed_logins=0, locked_until=NULL WHERE username=?",
            (hash_password(PASSWORD), USER),
        )
    else:
        db.execute(
            "INSERT INTO users(username, password_hash, role, created_at) VALUES(?,?,?,?)",
            (USER, hash_password(PASSWORD), "admin", time.time()),
        )
    db.commit()
    db.flush()
    upsert_env(ROOT / ".env", "FRAMEGENIUS_RESET_ADMIN", "0")
    account = write_account_file()
    print("Account saved")
    print(f"  operator   : {USER}")
    print(f"  passphrase : {PASSWORD}")
    print(f"  copy from  : {account}")
    print("  gate       : OFF — studio opens with no login")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
