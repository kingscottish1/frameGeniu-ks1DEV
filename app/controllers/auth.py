"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.security.auth import (
    COOKIE_NAME,
    CSRF_COOKIE,
    AuthUser,
    authenticate,
    auth_enabled,
    cookie_secure,
    create_api_key,
    require_auth,
    revoke_session,
)
from app.security.crypto import hash_password, verify_password
from app.security.db import get_db
from app.security.rate_limit import limiter
from app.utils.env import env

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class PasswordBody(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=256)


class KeyBody(BaseModel):
    name: str = Field(default="studio", min_length=1, max_length=64)


def _set_session_cookies(response: Response, user: AuthUser) -> None:
    secure = cookie_secure()
    response.set_cookie(
        COOKIE_NAME,
        user.session_id,
        httponly=True,
        samesite="lax",
        secure=secure,
        max_age=12 * 3600,
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        user.csrf,
        httponly=False,
        samesite="lax",
        secure=secure,
        max_age=12 * 3600,
        path="/",
    )


@router.get("/status")
def status() -> dict:
    from app.security.db import data_folder

    note = data_folder() / "FIRST_LOGIN.txt"
    user = "admin"
    password = ""
    if note.exists():
        for line in note.read_text(encoding="utf-8", errors="ignore").splitlines():
            low = line.lower()
            if low.startswith("user:"):
                user = line.split(":", 1)[1].strip() or "admin"
            if low.startswith("pass:"):
                password = line.split(":", 1)[1].strip()
    return {
        "auth": auth_enabled(),
        "first_boot": note.exists(),
        "username": user if note.exists() else "",
        "password": password,
        "hint": (
            f"Operator: {user}   Passphrase: {password}"
            if password
            else ("Open data\\FIRST_LOGIN.txt  or run FIX_LOGIN.bat" if note.exists() else "")
        ),
    }


@router.post("/login")
def login(body: LoginBody, request: Request, response: Response) -> dict:
    ip = request.client.host if request.client else ""
    if not limiter.allow(f"login-user:{body.username.lower()}", 8, 120):
        raise HTTPException(status_code=429, detail="Too many attempts")
    user = authenticate(body.username, body.password, ip=ip)
    _set_session_cookies(response, user)
    note = __import__("pathlib").Path(__import__("app.utils.file_manager", fromlist=["ROOT"]).ROOT) / "data" / "FIRST_LOGIN.txt"
    if note.exists():
        try:
            note.unlink()
        except OSError:
            pass
    return {"ok": True, "username": user.username, "role": user.role, "csrf": user.csrf}


@router.post("/logout")
def logout(request: Request, response: Response, user: AuthUser = Depends(require_auth)) -> dict:
    revoke_session(user.session_id)
    response.delete_cookie(COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    get_db().audit("logout", user=user.username)
    return {"ok": True}


@router.get("/me")
def me(user: AuthUser = Depends(require_auth)) -> dict:
    return {"username": user.username, "role": user.role, "csrf": user.csrf, "auth": auth_enabled()}


@router.post("/password")
def change_password(body: PasswordBody, user: AuthUser = Depends(require_auth)) -> dict:
    db = get_db()
    row = db.one("SELECT * FROM users WHERE id=?", (user.id,))
    if not row or not verify_password(body.current_password, row["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is wrong")
    if len(body.new_password) < 10:
        raise HTTPException(status_code=400, detail="New password must be at least 10 characters")
    db.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(body.new_password), user.id))
    db.commit()
    db.flush()
    db.audit("password_change", user=user.username)
    return {"ok": True}


@router.post("/api-keys")
def mint_key(body: KeyBody, user: AuthUser = Depends(require_auth)) -> dict:
    raw = create_api_key(user.id, body.name)
    get_db().audit("api_key_create", user=user.username, detail=body.name)
    return {"api_key": raw, "name": body.name, "note": "Store this now. It will not be shown again."}


@router.get("/api-keys")
def list_keys(user: AuthUser = Depends(require_auth)) -> dict:
    rows = get_db().query(
        "SELECT id, name, prefix, created_at, last_used, revoked FROM api_keys WHERE user_id=? ORDER BY created_at DESC",
        (user.id,),
    )
    return {
        "items": [
            {
                "id": row["id"],
                "name": row["name"],
                "prefix": row["prefix"],
                "created_at": row["created_at"],
                "last_used": row["last_used"],
                "revoked": bool(row["revoked"]),
            }
            for row in rows
        ]
    }
