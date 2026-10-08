"""Health check endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app import __author__, __version__
from app.config.settings import get_settings
from app.security.auth import AuthUser, resolve_user, COOKIE_NAME
from fastapi import Cookie, Header
from typing import Optional

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    ffmpeg_ok = False
    try:
        ffmpeg_ok = bool(settings.ffmpeg)
    except Exception:
        ffmpeg_ok = False
    return {
        "status": "ok",
        "name": "FrameGenius",
        "version": __version__,
        "ffmpeg": ffmpeg_ok,
    }


@router.get("/health/full")
def health_full(
    request: Request,
    fg_session: Optional[str] = Cookie(default=None, alias=COOKIE_NAME),
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> dict:
    user = resolve_user(request, fg_session, authorization, x_api_key)
    settings = get_settings()
    ffmpeg_ok = False
    try:
        ffmpeg_ok = bool(settings.ffmpeg)
    except Exception:
        ffmpeg_ok = False
    payload = {
        "status": "ok",
        "name": "FrameGenius",
        "version": __version__,
        "author": __author__,
        "ffmpeg": ffmpeg_ok,
        "authenticated": bool(user and user.username != "local" or user),
    }
    if user:
        payload["demo_mode"] = settings.llm_provider in {"demo", "local", "none"}
        payload["providers"] = {
            "llm": settings.llm_provider,
            "tts": settings.tts_provider,
            "media": settings.media_provider,
        }
        payload["user"] = user.username
    return payload


@router.get("/version")
def version() -> dict:
    return {"version": __version__, "author": __author__, "product": "FrameGenius"}
