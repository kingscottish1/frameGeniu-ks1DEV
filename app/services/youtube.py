"""YouTube Data API upload — free Google OAuth client, no paid API."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config.settings import get_settings
from app.utils.file_manager import ROOT
from app.utils.logger import get_logger

log = get_logger("youtube")

TOKEN_PATH = ROOT / "data" / "youtube_token.json"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
SCOPE = "https://www.googleapis.com/auth/youtube.upload"


def _cfg() -> dict:
    return get_settings().section("upload")


def credentials() -> tuple[str, str]:
    cfg = _cfg()
    cid = str(cfg.get("youtube_client_id") or "").strip()
    secret = str(cfg.get("youtube_client_secret") or "").strip()
    return cid, secret


def configured() -> bool:
    cid, secret = credentials()
    return bool(cid and secret and "****" not in secret and "****" not in cid)


def connected() -> bool:
    data = _load_token()
    return bool(data.get("refresh_token") or data.get("access_token"))


def _load_token() -> dict[str, Any]:
    if not TOKEN_PATH.exists():
        return {}
    try:
        return json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_token(data: dict[str, Any]) -> None:
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        TOKEN_PATH.chmod(0o600)
    except OSError:
        pass


def auth_url(redirect_uri: str) -> str:
    cid, _secret = credentials()
    if not cid:
        return ""
    params = {
        "client_id": cid,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    return AUTH_URL + "?" + urlencode(params)


def exchange_code(code: str, redirect_uri: str) -> dict[str, Any]:
    cid, secret = credentials()
    resp = httpx.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": cid,
            "client_secret": secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    payload["obtained_at"] = time.time()
    existing = _load_token()
    if not payload.get("refresh_token") and existing.get("refresh_token"):
        payload["refresh_token"] = existing["refresh_token"]
    _save_token(payload)
    return payload


def _access_token() -> str:
    data = _load_token()
    token = str(data.get("access_token") or "")
    obtained = float(data.get("obtained_at") or 0)
    expires = float(data.get("expires_in") or 3600)
    if token and time.time() < obtained + expires - 60:
        return token
    refresh = str(data.get("refresh_token") or "")
    if not refresh:
        return token
    cid, secret = credentials()
    resp = httpx.post(
        TOKEN_URL,
        data={
            "client_id": cid,
            "client_secret": secret,
            "refresh_token": refresh,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    resp.raise_for_status()
    fresh = resp.json()
    data.update(fresh)
    data["obtained_at"] = time.time()
    _save_token(data)
    return str(data.get("access_token") or "")


def upload_video(
    path: Path,
    *,
    title: str,
    description: str = "",
    tags: list[str] | None = None,
    privacy: str = "unlisted",
) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise RuntimeError("Video file missing.")
    token = _access_token()
    if not token:
        raise RuntimeError("YouTube is not connected.")
    privacy = privacy if privacy in {"public", "unlisted", "private"} else "unlisted"
    snippet = {
        "title": (title or path.stem)[:100],
        "description": (description or "")[:4900],
        "tags": [str(t).lstrip("#")[:30] for t in (tags or [])[:15]],
        "categoryId": "22",
    }
    meta = {"snippet": snippet, "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}}
    size = path.stat().st_size
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Length": str(size),
        "X-Upload-Content-Type": "video/mp4",
    }
    init = httpx.post(
        UPLOAD_URL,
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers=headers,
        json=meta,
        timeout=60,
    )
    init.raise_for_status()
    location = init.headers.get("Location") or init.headers.get("location")
    if not location:
        raise RuntimeError("YouTube did not start a resumable upload.")
    with path.open("rb") as handle:
        put = httpx.put(
            location,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "video/mp4",
                "Content-Length": str(size),
            },
            content=handle,
            timeout=600,
        )
    put.raise_for_status()
    body = put.json() if put.content else {}
    video_id = str(body.get("id") or "")
    watch = f"https://youtu.be/{video_id}" if video_id else ""
    log.info("Uploaded {} to YouTube as {}", path.name, video_id or "?")
    return {
        "ok": True,
        "platform": "youtube",
        "video_id": video_id,
        "watch_url": watch,
        "privacy": privacy,
        "title": snippet["title"],
    }
