"""First-run hardening: master key, admin user, encrypted DB, file perms."""

from __future__ import annotations

import os
import time
from pathlib import Path

from app.security.crypto import (
    ensure_master_key,
    hash_password,
    strong_password,
    upsert_env,
    _chmod_private,
)
from app.security.db import get_db
from app.utils.env import env, load_env
from app.utils.file_manager import ROOT
from app.utils.logger import get_logger

log = get_logger("bootstrap")

DEFAULT_ADMIN_PASSWORD = "FrameGenius!"


def bootstrap(root: Path | None = None) -> dict:
    base = Path(root) if root else ROOT
    load_env(base)
    ensure_master_key(base)
    from app.security.db import data_folder

    data = data_folder()
    data.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(data, 0o700)
    except OSError:
        pass

    for sensitive in (base / ".env", base / "config.toml"):
        if sensitive.exists():
            _chmod_private(sensitive)

    db = get_db()
    username = (env("FRAMEGENIUS_ADMIN_USER") or "admin").strip().lower()
    password = env("FRAMEGENIUS_ADMIN_PASSWORD")
    created = False
    row = db.one("SELECT id FROM users WHERE username=?", (username,))
    if not row:
        if not password:
            password = DEFAULT_ADMIN_PASSWORD
            upsert_env(base / ".env", "FRAMEGENIUS_ADMIN_USER", username)
            upsert_env(base / ".env", "FRAMEGENIUS_ADMIN_PASSWORD", password)
        db.execute(
            "INSERT INTO users(username, password_hash, role, created_at) VALUES(?,?,?,?)",
            (username, hash_password(password), "admin", time.time()),
        )
        db.commit()
        db.flush()
        created = True
        note = data / "FIRST_LOGIN.txt"
        note.write_text(
            "FrameGenius first-boot credentials — delete after login.\n"
            f"user: {username}\n"
            f"pass: {password}\n"
            "Change this password immediately.\n",
            encoding="utf-8",
        )
        _chmod_private(note)
        log.info("Created admin user '{}'. Credentials written to data/FIRST_LOGIN.txt", username)
    elif password:
        # keep hash in sync if env password was rotated on purpose and user asked via RESET flag
        if env("FRAMEGENIUS_RESET_ADMIN") == "1":
            db.execute(
                "UPDATE users SET password_hash=?, failed_logins=0, locked_until=NULL WHERE username=?",
                (hash_password(password), username),
            )
            db.commit()
            db.flush()
            log.info("Admin password reset from environment")

    db.audit("bootstrap", user="system", detail="ok" if not created else "admin-created")
    return {
        "admin": username,
        "created": created,
        "vault_recovered": bool(getattr(db, "recovered", False)),
    }
