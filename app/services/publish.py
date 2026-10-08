"""Post a finished film to YouTube or pack it for TikTok."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config.settings import get_settings
from app.services import task as task_service
from app.services import upload as upload_service
from app.services import youtube
from app.services.video import find_task_video
from app.utils.logger import get_logger

log = get_logger("publish")


def status() -> dict[str, Any]:
    settings = get_settings()
    cfg = settings.section("upload")
    whisper = _whisper_status()
    keys = [k for k in (settings.media.get("pexels_api_keys") or []) if k and "****" not in str(k)]
    return {
        "youtube_configured": youtube.configured(),
        "youtube_connected": youtube.connected(),
        "tiktok_upload_post": bool(str(cfg.get("upload_post_api_key") or "").strip()),
        "pexels": bool(keys),
        "coverr": True,
        "whisper": whisper,
    }


def _whisper_status() -> dict[str, bool]:
    faster = False
    vosk = False
    openai = False
    try:
        import faster_whisper  # noqa: F401

        faster = True
    except Exception:
        pass
    try:
        import vosk  # noqa: F401

        vosk = True
    except Exception:
        pass
    try:
        import whisper  # noqa: F401

        openai = True
    except Exception:
        pass
    return {"faster_whisper": faster, "vosk": vosk, "openai_whisper": openai, "ready": faster or vosk or openai}


def publish_task(task_id: str, *, platform: str, privacy: str = "unlisted") -> dict[str, Any]:
    record = task_service.get_task(task_id)
    if not record:
        raise RuntimeError("Task not found.")
    path = None
    if record.result.get("video_path"):
        p = Path(str(record.result["video_path"]))
        if p.exists():
            path = p
    if path is None:
        path = find_task_video(task_id)
    if path is None or not Path(path).exists():
        raise RuntimeError("Video file is not ready.")
    path = Path(path)
    title = str(record.result.get("title") or (record.params or {}).get("topic") or path.stem)
    description = ""
    kit = record.result.get("postkit") or {}
    if isinstance(kit, dict):
        description = str(kit.get("description") or kit.get("caption") or "")
        if not title or title == path.stem:
            titles = kit.get("titles") or []
            if titles:
                title = str(titles[0])
    tags = record.result.get("hashtags") or record.result.get("tags") or kit.get("hashtags") or []
    tags = [str(t) for t in tags]
    hook = str(record.result.get("hook") or "")
    if hook and hook not in description:
        description = (hook + "\n\n" + description).strip()
    platform = (platform or "").lower().strip()
    if platform in {"youtube", "yt"}:
        if not youtube.configured():
            return {
                "ok": False,
                "need_auth": False,
                "need_client": True,
                "message": "Paste a free Google OAuth client id + secret in Settings first.",
            }
        if not youtube.connected():
            return {
                "ok": False,
                "need_auth": True,
                "message": "Connect YouTube in Settings, then try again.",
            }
        return youtube.upload_video(
            path, title=title, description=description, tags=tags, privacy=privacy
        )
    if platform in {"tiktok", "tt"}:
        cfg = get_settings().section("upload")
        if str(cfg.get("upload_post_api_key") or "").strip():
            rec = upload_service.publish(
                path,
                title=title,
                description=description,
                platforms=["tiktok"],
                tags=tags,
            )
            rec["ok"] = True
            rec["platform"] = "tiktok"
            return rec
        caption = title
        if description:
            caption = f"{title}\n\n{description}".strip()
        if tags:
            caption = caption + "\n\n" + " ".join(tags)
        return {
            "ok": True,
            "platform": "tiktok",
            "mode": "studio",
            "caption": caption[:2200],
            "file": str(path),
            "studio_url": "https://www.tiktok.com/tiktokstudio/upload",
            "message": "Caption ready. TikTok Studio will open — drop the file.",
        }
    raise RuntimeError(f"Unknown platform: {platform}")
