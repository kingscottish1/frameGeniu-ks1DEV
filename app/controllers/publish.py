"""YouTube + TikTok publish endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.security.auth import AuthUser, require_auth
from app.security.db import get_db
from app.security.paths import is_safe_task_id
from app.services import publish as publish_service
from app.services import youtube

router = APIRouter(prefix="/publish", tags=["publish"])


class PublishBody(BaseModel):
    platform: str = Field("youtube")
    privacy: str = Field("unlisted")


def _redirect_uri(request: Request) -> str:
    return str(request.base_url).rstrip("/") + "/api/v1/publish/youtube/callback"


@router.get("/status")
def status(user: AuthUser = Depends(require_auth)) -> dict:
    return publish_service.status()


@router.get("/youtube/auth")
def youtube_auth(request: Request, user: AuthUser = Depends(require_auth)) -> dict:
    if not youtube.configured():
        raise HTTPException(
            status_code=400,
            detail="Paste a free Google OAuth client id + secret in Settings first.",
        )
    url = youtube.auth_url(_redirect_uri(request))
    return {"ok": True, "auth_url": url}


@router.get("/youtube/callback")
def youtube_callback(request: Request, code: str = "", error: str = "") -> HTMLResponse:
    if error:
        return HTMLResponse(
            f"<html><body style='font-family:sans-serif;background:#050506;color:#f4eee8;padding:2rem'>"
            f"<h2>YouTube connect failed</h2><p>{error}</p></body></html>",
            status_code=400,
        )
    if not code:
        raise HTTPException(status_code=400, detail="Missing code")
    try:
        youtube.exchange_code(code, _redirect_uri(request))
    except Exception as exc:
        return HTMLResponse(
            f"<html><body style='font-family:sans-serif;background:#050506;color:#f4eee8;padding:2rem'>"
            f"<h2>YouTube connect failed</h2><p>{exc}</p></body></html>",
            status_code=400,
        )
    get_db().audit("youtube_connect", user="studio")
    return HTMLResponse(
        "<html><body style='font-family:sans-serif;background:#050506;color:#f4eee8;padding:2rem'>"
        "<h2>YouTube connected</h2><p>You can close this tab and go back to FrameGenius.</p></body></html>"
    )


@router.post("/{task_id}")
def publish(task_id: str, body: PublishBody, user: AuthUser = Depends(require_auth)) -> dict:
    if not is_safe_task_id(task_id):
        raise HTTPException(status_code=400, detail="Bad task id")
    try:
        result = publish_service.publish_task(
            task_id, platform=body.platform, privacy=body.privacy
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    get_db().audit("publish", user=user.username, detail=f"{body.platform}:{task_id}")
    return result
