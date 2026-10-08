"""Channel kit — one show identity for every film."""

from __future__ import annotations

from app.config.settings import get_settings, save_settings
from app.models.video import VideoParams

DEFAULTS = {
    "name": "FrameGenius",
    "handle": "",
    "voice": "",
    "watermark": True,
    "intro_enabled": True,
    "cta_enabled": True,
    "cta_text": "Sub and follow.",
    "default_template": "auto",
    "default_aspect": "9:16",
}


def load_channel() -> dict:
    raw = get_settings().section("channel")
    out = dict(DEFAULTS)
    for key, value in DEFAULTS.items():
        if key in raw and raw[key] not in {None, ""}:
            out[key] = raw[key]
        elif key in raw and isinstance(value, bool):
            out[key] = bool(raw[key])
    out["watermark"] = bool(raw.get("watermark", out["watermark"]))
    out["intro_enabled"] = bool(raw.get("intro_enabled", out["intro_enabled"]))
    out["cta_enabled"] = bool(raw.get("cta_enabled", out["cta_enabled"]))
    return out


def save_channel(values: dict) -> dict:
    clean = {}
    for key in DEFAULTS:
        if key not in values:
            continue
        val = values[key]
        if isinstance(DEFAULTS[key], bool):
            clean[key] = bool(val)
        else:
            clean[key] = str(val or "").strip()
    save_settings({"channel": clean})
    return load_channel()


def apply_channel(params: VideoParams) -> VideoParams:
    """Stamp brand defaults onto a job without wiping the user's form."""
    ch = load_channel()
    data = params.model_dump()
    if ch.get("watermark"):
        data["watermark"] = True
    if "intro_enabled" not in data or data.get("intro_enabled") is None:
        data["intro_enabled"] = bool(ch.get("intro_enabled", True))
    if "cta_enabled" not in data or data.get("cta_enabled") is None:
        data["cta_enabled"] = bool(ch.get("cta_enabled", True))
    if ch.get("voice") and not data.get("voice"):
        data["voice"] = ch["voice"]
    return VideoParams.model_validate(data)


def brand_label() -> str:
    name = str(load_channel().get("name") or "FrameGenius").strip()
    return name[:32] or "FrameGenius"


def cta_line() -> str:
    text = str(load_channel().get("cta_text") or "Sub and follow.").strip()
    if "come back" in text.lower() or "full picture" in text.lower() or "next file" in text.lower():
        return "Sub and follow."
    return text[:80] or "Sub and follow."
