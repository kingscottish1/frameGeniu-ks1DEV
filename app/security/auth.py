"""Session + API-key authentication."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from fastapi import Cookie, Header, HTTPException, Request

from app.security.crypto import hash_secret, random_token, verify_password
from app.security.db import get_db
from app.utils.env import env, env_bool

SESSION_HOURS = 12
COOKIE_NAME = "fg_session"
CSRF_COOKIE = "fg_csrf"
MAX_FAILED = 8
LOCK_SECONDS = 15 * 60


@dataclass
class AuthUser:
    id: int
    username: str
    role: str
    csrf: str
    session_id: str


def auth_enabled() -> bool:
    # Always open locally — MoneyPrinterTurbo style. API keys go in Settings.
    return False


def cookie_secure() -> bool:
    return env_bool("FRAMEGENIUS_COOKIE_SECURE", False)


def get_user_by_name(username: str):
    return get_db().one("SELECT * FROM users WHERE username = ?", (username.lower(),))


def authenticate(username: str, password: str, *, ip: str = "") -> AuthUser:
    db = get_db()
    row = get_user_by_name(username)
    if not row:
        db.audit("login_unknown", user=username, ip=ip)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    now = time.time()
    if row["locked_until"] and float(row["locked_until"]) > now:
        raise HTTPException(status_code=423, detail="Account temporarily locked")
    if not verify_password(password, row["password_hash"]):
        fails = int(row["failed_logins"] or 0) + 1
        locked = now + LOCK_SECONDS if fails >= MAX_FAILED else None
        db.execute(
            "UPDATE users SET failed_logins=?, locked_until=? WHERE id=?",
            (fails, locked, row["id"]),
        )
        db.commit()
        db.audit("login_failed", user=row["username"], ip=ip)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    db.execute(
        "UPDATE users SET failed_logins=0, locked_until=NULL, last_login=? WHERE id=?",
        (now, row["id"]),
    )
    db.commit()
    session = issue_session(int(row["id"]), ip=ip, user_agent="")
    db.audit("login_ok", user=row["username"], ip=ip)
    return session


def issue_session(user_id: int, *, ip: str = "", user_agent: str = "") -> AuthUser:
    db = get_db()
    user = db.one("SELECT * FROM users WHERE id=?", (user_id,))
    if not user:
        raise HTTPException(status_code=401, detail="User missing")
    raw = random_token(32)
    csrf = random_token(18)
    sid = random_token(12)
    now = time.time()
    db.execute(
        "INSERT INTO sessions(id, user_id, token_hash, csrf, created_at, expires_at, ip, user_agent) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (sid, user_id, hash_secret(raw), csrf, now, now + SESSION_HOURS * 3600, ip, user_agent[:240]),
    )
    db.commit()
    # raw token is returned as cookie value: session_id.raw
    token = f"{sid}.{raw}"
    return AuthUser(
        id=int(user["id"]),
        username=user["username"],
        role=user["role"],
        csrf=csrf,
        session_id=token,
    )


def _parse_session(token: str | None) -> AuthUser | None:
    if not token or "." not in token:
        return None
    sid, raw = token.split(".", 1)
    db = get_db()
    row = db.one("SELECT * FROM sessions WHERE id=?", (sid,))
    if not row:
        return None
    if float(row["expires_at"]) < time.time():
        db.execute("DELETE FROM sessions WHERE id=?", (sid,))
        db.commit()
        return None
    if hash_secret(raw) != row["token_hash"]:
        return None
    user = db.one("SELECT * FROM users WHERE id=?", (row["user_id"],))
    if not user:
        return None
    return AuthUser(
        id=int(user["id"]),
        username=user["username"],
        role=user["role"],
        csrf=row["csrf"],
        session_id=token,
    )


def _parse_api_key(header: str | None) -> AuthUser | None:
    if not header:
        return None
    key = header.strip()
    if key.lower().startswith("bearer "):
        key = key[7:].strip()
    digest = hash_secret(key)
    db = get_db()
    row = db.one("SELECT * FROM api_keys WHERE key_hash=? AND revoked=0", (digest,))
    if not row:
        return None
    db.execute("UPDATE api_keys SET last_used=? WHERE id=?", (time.time(), row["id"]))
    db.commit()
    user = db.one("SELECT * FROM users WHERE id=?", (row["user_id"],))
    if not user:
        return None
    return AuthUser(
        id=int(user["id"]),
        username=user["username"],
        role=user["role"],
        csrf="",
        session_id="",
    )


def resolve_user(
    request: Request,
    fg_session: Optional[str] = None,
    authorization: Optional[str] = None,
    x_api_key: Optional[str] = None,
) -> AuthUser | None:
    if not auth_enabled():
        return AuthUser(id=0, username="local", role="admin", csrf="dev", session_id="")
    user = _parse_session(fg_session)
    if user:
        return user
    return _parse_api_key(x_api_key or authorization)


def require_auth(
    request: Request,
    fg_session: Optional[str] = Cookie(default=None, alias=COOKIE_NAME),
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    x_csrf_token: Optional[str] = Header(default=None, alias="X-CSRF-Token"),
) -> AuthUser:
    user = resolve_user(request, fg_session, authorization, x_api_key)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if (
        auth_enabled()
        and request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and user.csrf
        and request.url.path.startswith("/api/")
        and not (x_api_key or (authorization or "").lower().startswith("bearer "))
    ):
        if not x_csrf_token or x_csrf_token != user.csrf:
            raise HTTPException(status_code=403, detail="CSRF check failed")
    request.state.user = user
    return user


def current_user(request: Request) -> AuthUser | None:
    return getattr(request.state, "user", None)


def revoke_session(token: str | None) -> None:
    if not token or "." not in token:
        return
    sid = token.split(".", 1)[0]
    db = get_db()
    db.execute("DELETE FROM sessions WHERE id=?", (sid,))
    db.commit()


def create_api_key(user_id: int, name: str) -> str:
    raw = "fg_" + random_token(24)
    db = get_db()
    db.execute(
        "INSERT INTO api_keys(id, user_id, name, prefix, key_hash, created_at) VALUES(?,?,?,?,?,?)",
        (random_token(8), user_id, name[:64], raw[:10], hash_secret(raw), time.time()),
    )
    db.commit()
    db.flush()
    return raw
