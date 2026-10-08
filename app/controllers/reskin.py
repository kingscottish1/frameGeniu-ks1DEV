"""Upload a film → bleep swears → new pictures on the cleaned sound."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.models.video import AspectRatio, VideoParams
from app.security.auth import AuthUser, require_auth
from app.security.db import get_db
from app.services import task as task_service
from app.services.video import probe_duration
from app.utils.exceptions import FrameGeniusError
from app.utils.file_manager import ROOT
from app.utils.validators import safe_filename

router = APIRouter(prefix="/reskin", tags=["reskin"])

_OK = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}
_MAX = 400 * 1024 * 1024


@router.post("")
async def reskin(
    file: UploadFile = File(...),
    topic: str = Form(""),
    aspect_ratio: str = Form("9:16"),
    bleep: str = Form("1"),
    user: AuthUser = Depends(require_auth),
) -> dict:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(raw) > _MAX:
        raise HTTPException(status_code=400, detail="Video too large (400 MB max).")
    name = safe_filename(file.filename or "upload.mp4", fallback="upload.mp4")
    suffix = Path(name).suffix.lower()
    if suffix not in _OK:
        raise HTTPException(status_code=400, detail="Use mp4, mov, mkv or webm.")
    folder = ROOT / "outputs" / "uploads"
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / name
    dest.write_bytes(raw)
    duration = probe_duration(dest) or 30.0
    duration = float(min(1800.0, max(8.0, duration)))
    topic = (topic or "").strip() or Path(name).stem.replace("_", " ").replace("-", " ")
    if len(topic) < 2:
        topic = "uploaded film"
    try:
        aspect = AspectRatio(aspect_ratio)
    except Exception:
        aspect = AspectRatio.PORTRAIT
    params = VideoParams(
        topic=topic[:240],
        template="story",
        aspect_ratio=aspect,
        duration=duration,
        research_enabled=False,
        subtitle_enabled=True,
        bgm_enabled=False,
        intro_enabled=False,
        cta_enabled=False,
        hook_lock=False,
        cut_shorts=False,
        dual_export=True,
        source_video=str(dest),
        bleep_profanity=bleep.strip() not in {"0", "false", "off", "no"},
    )
    try:
        record = task_service.submit(params)
    except FrameGeniusError as exc:
        raise HTTPException(status_code=400, detail=exc.to_dict()) from exc
    get_db().audit("reskin", user=user.username, detail=topic[:120])
    return record.as_public()
