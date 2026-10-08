"""Social upload service. Uses Upload-Post when a key is present."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from app.config.settings import get_settings
from app.utils.exceptions import ProviderError
from app.utils.logger import get_logger

log = get_logger("upload")


def publish(
    video_path: str | Path,
    *,
    title: str,
    description: str = "",
    platforms: list[str] | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    cfg = settings.section("upload")
    provider = str(cfg.get("provider") or "").lower()
    video_path = Path(video_path)
    if not video_path.exists():
        raise ProviderError("Video file does not exist.", stage="upload")
    targets = platforms or list(cfg.get("default_platforms") or ["youtube"])
    if provider in {"", "none", "local"}:
        receipt = {
            "status": "prepared",
            "provider": "local",
            "title": title,
            "description": description,
            "platforms": targets,
            "tags": tags or [],
            "file": str(video_path),
            "message": "No upload provider configured. File is ready to publish manually.",
        }
        log.info("Prepared local publish receipt for {}", video_path.name)
        return receipt
    if provider in {"upload-post", "upload_post", "uploadpost"}:
        return _upload_post(video_path, title, description, targets, tags or [], cfg)
    raise ProviderError(f"Unknown upload provider: {provider}", stage="upload")


def _upload_post(
    video_path: Path,
    title: str,
    description: str,
    platforms: list[str],
    tags: list[str],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    api_key = str(cfg.get("upload_post_api_key") or "")
    if not api_key:
        raise ProviderError("Upload-Post API key is missing.", stage="upload")
    base = str(cfg.get("upload_post_base_url") or "https://api.upload-post.com").rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}"}
    data = {
        "title": title,
        "description": description,
        "platforms": ",".join(platforms),
        "tags": ",".join(tags),
    }
    try:
        with video_path.open("rb") as handle:
            response = httpx.post(
                f"{base}/api/upload",
                headers=headers,
                data=data,
                files={"file": (video_path.name, handle, "video/mp4")},
                timeout=180,
            )
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        raise ProviderError(f"Upload-Post failed: {exc}", stage="upload") from exc
    payload.setdefault("status", "submitted")
    payload.setdefault("provider", "upload-post")
    return payload
