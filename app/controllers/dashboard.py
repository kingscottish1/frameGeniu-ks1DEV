"""Dashboard stats and security overview."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter, Depends

from app import __author__, __version__
from app.config.settings import get_settings
from app.security.auth import AuthUser, require_auth
from app.security.crypto import get_vault
from app.security.db import get_db
from app.services import task as task_service
from app.utils.file_manager import ROOT

router = APIRouter(prefix="/studio", tags=["studio"])


@router.get("/stats")
def stats(user: AuthUser = Depends(require_auth)) -> dict:
    tasks = task_service.list_tasks()
    done = [t for t in tasks if str(t.state) in {"completed", "TaskState.COMPLETED"} or getattr(t.state, "value", "") == "completed"]
    fail = [t for t in tasks if getattr(t.state, "value", str(t.state)) == "failed"]
    busy = [t for t in tasks if getattr(t.state, "value", str(t.state)) == "processing"]
    settings = get_settings()
    videos = list(settings.files.videos.glob("*.mp4"))
    bytes_out = sum(p.stat().st_size for p in videos)
    db = get_db()
    sessions = db.query("SELECT COUNT(*) AS n FROM sessions WHERE expires_at > ?", (time.time(),))
    audits = db.query("SELECT action, ts, user FROM audit ORDER BY ts DESC LIMIT 12")
    return {
        "product": "FrameGenius",
        "author": __author__,
        "version": __version__,
        "user": user.username,
        "totals": {
            "renders": len(done),
            "failed": len(fail),
            "inflight": len(busy),
            "jobs": len(tasks),
            "library_bytes": bytes_out,
            "library_files": len(videos),
        },
        "providers": {
            "llm": settings.llm_provider,
            "tts": settings.tts_provider,
            "media": settings.media_provider,
        },
        "security": {
            "encrypted_db": (ROOT / "data" / "framegenius.db.enc").exists(),
            "key_fingerprint": get_vault().fingerprint(),
            "active_sessions": int(sessions[0]["n"]) if sessions else 0,
            "auth": True,
        },
        "audit": [{"action": r["action"], "ts": r["ts"], "user": r["user"]} for r in audits],
        "recent": [t.as_public() for t in tasks[:8]],
        "crew": _crew(),
    }


@router.get("/crew")
def crew(user: AuthUser = Depends(require_auth)) -> dict:
    return {"agents": _crew()}


def _crew() -> list[dict]:
    from app.agents.orchestrator import DEFAULT_CREW

    return [{"name": cls.name, "label": cls.label} for cls in DEFAULT_CREW]


@router.get("/security")
def security(user: AuthUser = Depends(require_auth)) -> dict:
    enc = ROOT / "data" / "framegenius.db.enc"
    return {
        "database": {
            "path": "data/framegenius.db.enc",
            "exists": enc.exists(),
            "bytes": enc.stat().st_size if enc.exists() else 0,
            "cipher": "AES-256-GCM",
            "kdf": "HKDF-SHA256",
        },
        "key_fingerprint": get_vault().fingerprint(),
        "files": {
            "env_mode": _mode(ROOT / ".env"),
            "config_mode": _mode(ROOT / "config.toml"),
            "data_mode": _mode(ROOT / "data"),
        },
        "user": user.username,
        "role": user.role,
    }


@router.get("/preflight")
def preflight(user: AuthUser = Depends(require_auth)) -> dict:
    """What the studio can actually do on this machine right now."""
    import shutil
    import subprocess

    settings = get_settings()
    ffmpeg_path = ""
    ffmpeg_ok = False
    filters: list[str] = []
    try:
        ffmpeg_path = settings.ffmpeg
        ffmpeg_ok = bool(ffmpeg_path)
        if ffmpeg_ok:
            probe = subprocess.run(
                [ffmpeg_path, "-hide_banner", "-filters"],
                capture_output=True,
                text=True,
                timeout=8,
            )
            blob = probe.stdout or ""
            for name in ("ass", "subtitles", "drawtext", "xfade", "zoompan"):
                if re_has_filter(blob, name):
                    filters.append(name)
    except Exception:
        ffmpeg_ok = False

    ollama_online = False
    ollama_models: list[str] = []
    try:
        from app.providers.llm.ollama import OllamaLLM

        client = OllamaLLM(base_url=str(settings.llm.get("ollama_base_url") or "http://127.0.0.1:11434"))
        ollama_online = client.ping()
        ollama_models = client.list_models() if ollama_online else []
    except Exception:
        pass

    videos = list(settings.files.videos.glob("*.mp4"))
    disk_free = 0
    try:
        disk_free = shutil.disk_usage(str(settings.root)).free
    except OSError:
        pass
    pub: dict = {}
    try:
        from app.services import publish as publish_service

        pub = publish_service.status()
    except Exception:
        pub = {}
    whisper = pub.get("whisper") if isinstance(pub.get("whisper"), dict) else {}
    return {
        "ffmpeg": ffmpeg_ok,
        "ffmpeg_path": ffmpeg_path,
        "ffmpeg_filters": filters,
        "ollama": ollama_online,
        "ollama_models": ollama_models,
        "ollama_model": str(settings.llm.get("ollama_model") or "gemma4:latest"),
        "tts": settings.tts_provider,
        "media": settings.media_provider,
        "llm": settings.llm_provider,
        "fonts": len(list(settings.files.fonts.glob("*.ttf"))),
        "songs": len(settings.files.list_songs()),
        "local_media": len(settings.files.list_local_media()),
        "library_files": len(videos),
        "disk_free_mb": int(disk_free / (1024 * 1024)),
        "auth": False,
        "studio_url": f"http://127.0.0.1:{settings.port}",
        "whisper": bool(whisper.get("ready")),
        "whisper_engines": whisper,
        "pexels": bool(pub.get("pexels")),
        "coverr": True,
        "youtube": bool(pub.get("youtube_connected")),
        "youtube_configured": bool(pub.get("youtube_configured")),
    }


def re_has_filter(blob: str, name: str) -> bool:
    return f" {name} " in f" {blob} " or f" {name}\n" in blob or f"\n{name} " in blob


def _mode(path: Path) -> str:
    if not path.exists():
        return "missing"
    try:
        return oct(path.stat().st_mode & 0o777)
    except OSError:
        return "unknown"
