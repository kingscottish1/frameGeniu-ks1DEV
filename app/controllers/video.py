"""Video generation endpoints — stream for the player, download for the file."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from app.models.task import TaskCreate
from app.models.video import VideoParams
from app.security.auth import AuthUser, require_auth
from app.security.db import get_db
from app.security.paths import is_safe_task_id, safe_under
from app.services import task as task_service
from app.services.video import find_task_video
from app.utils.exceptions import FrameGeniusError, ValidationError
from app.utils.file_manager import ROOT

router = APIRouter(prefix="/videos", tags=["videos"])


def _resolve_video(task_id: str) -> Path:
    record = task_service.get_task(task_id)
    candidates: list[str] = []
    if record and record.result.get("video_path"):
        candidates.append(str(record.result["video_path"]))
    found = find_task_video(task_id)
    if found:
        candidates.append(str(found))
    for raw in candidates:
        try:
            return safe_under(raw, ROOT / "outputs" / "videos", ROOT / "outputs")
        except ValidationError:
            continue
    raise HTTPException(status_code=404, detail="Video not ready")


@router.post("")
def create_video(body: TaskCreate | VideoParams, user: AuthUser = Depends(require_auth)) -> dict:
    params = body.params if isinstance(body, TaskCreate) else body
    try:
        record = task_service.submit(params)
    except FrameGeniusError as exc:
        raise HTTPException(status_code=400, detail=exc.to_dict()) from exc
    get_db().audit("video_create", user=user.username, detail=params.topic[:120])
    return record.as_public()


@router.get("/{task_id}/download")
def download_video(task_id: str, user: AuthUser = Depends(require_auth)):
    if not is_safe_task_id(task_id):
        raise HTTPException(status_code=400, detail="Bad task id")
    path = _resolve_video(task_id)
    return FileResponse(
        path,
        media_type="video/mp4",
        filename=path.name,
        headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
    )


@router.get("/{task_id}/stream")
def stream_video(task_id: str, user: AuthUser = Depends(require_auth)):
    if not is_safe_task_id(task_id):
        raise HTTPException(status_code=400, detail="Bad task id")
    path = _resolve_video(task_id)
    return FileResponse(
        path,
        media_type="video/mp4",
        filename=path.name,
        headers={"Content-Disposition": f'inline; filename="{path.name}"'},
    )


@router.get("/{task_id}/kit")
def download_kit(task_id: str, user: AuthUser = Depends(require_auth)):
    if not is_safe_task_id(task_id):
        raise HTTPException(status_code=400, detail="Bad task id")
    record = task_service.get_task(task_id)
    candidates = []
    if record and record.result.get("kit_path"):
        candidates.append(record.result["kit_path"])
    packed = ROOT / "outputs" / "videos" / f"{task_id}_postkit.zip"
    candidates.append(str(packed))
    work = ROOT / "outputs" / "tasks" / task_id / "POST.md"
    for raw in candidates:
        try:
            path = safe_under(raw, ROOT / "outputs" / "videos", ROOT / "outputs")
            return FileResponse(
                path,
                media_type="application/zip",
                filename=path.name,
                headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
            )
        except ValidationError:
            continue
    if work.exists():
        return FileResponse(work, media_type="text/markdown", filename="POST.md")
    raise HTTPException(status_code=404, detail="Post kit not ready")


@router.get("/{task_id}/captions")
def download_captions(task_id: str, user: AuthUser = Depends(require_auth)):
    if not is_safe_task_id(task_id):
        raise HTTPException(status_code=400, detail="Bad task id")
    srt = ROOT / "outputs" / "tasks" / task_id / "subtitles.srt"
    if not srt.exists():
        raise HTTPException(status_code=404, detail="Captions not ready")
    return FileResponse(srt, media_type="application/x-subrip", filename=f"{task_id}.srt")


@router.get("/{task_id}/tags")
def download_tags(task_id: str, user: AuthUser = Depends(require_auth)):
    if not is_safe_task_id(task_id):
        raise HTTPException(status_code=400, detail="Bad task id")
    path = ROOT / "outputs" / "tasks" / task_id / "hashtags.txt"
    if path.exists():
        return FileResponse(path, media_type="text/plain", filename=f"{task_id}_tags.txt")
    record = task_service.get_task(task_id)
    tags = []
    if record:
        tags = record.result.get("hashtags") or record.result.get("tags") or []
    if not tags:
        raise HTTPException(status_code=404, detail="Tags not ready")
    body = " ".join(str(item) for item in tags) + "\n"
    return PlainTextResponse(body, headers={"Content-Disposition": f'attachment; filename="{task_id}_tags.txt"'})


@router.get("/{task_id}/wide")
def download_wide(task_id: str, user: AuthUser = Depends(require_auth)):
    if not is_safe_task_id(task_id):
        raise HTTPException(status_code=400, detail="Bad task id")
    path = ROOT / "outputs" / "videos" / f"wide-{task_id}.mp4"
    if path.exists():
        return FileResponse(
            path,
            media_type="video/mp4",
            filename=path.name,
            headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
        )
    raise HTTPException(status_code=404, detail="Wide cut not ready")


@router.get("/{task_id}/shorts")
def download_shorts(task_id: str, user: AuthUser = Depends(require_auth)):
    if not is_safe_task_id(task_id):
        raise HTTPException(status_code=400, detail="Bad task id")
    packed = ROOT / "outputs" / "videos" / f"{task_id}_shorts.zip"
    if packed.exists():
        return FileResponse(
            packed,
            media_type="application/zip",
            filename=packed.name,
            headers={"Content-Disposition": f'attachment; filename="{packed.name}"'},
        )
    raise HTTPException(status_code=404, detail="No shorts for this film")


@router.get("/{task_id}/thumbnail")
def download_thumb(task_id: str, user: AuthUser = Depends(require_auth)):
    if not is_safe_task_id(task_id):
        raise HTTPException(status_code=400, detail="Bad task id")
    record = task_service.get_task(task_id)
    if not record:
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        path = safe_under(
            record.result.get("thumbnail_path") or "",
            ROOT / "outputs" / "thumbnails",
            ROOT / "outputs",
        )
        return FileResponse(path, media_type="image/jpeg", filename=path.name)
    except Exception:
        fallback = ROOT / "resource" / "icons" / "logo.png"
        if fallback.exists():
            return FileResponse(fallback, media_type="image/png", filename="thumb.png")
        raise HTTPException(status_code=404, detail="Thumbnail missing")
