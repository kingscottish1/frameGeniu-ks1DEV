"""Input validation helpers."""

from __future__ import annotations

import re

from app.utils.exceptions import ValidationError

_ASPECTS = {"9:16", "16:9", "1:1", "4:5", "21:9"}
_TOPIC_RE = re.compile(r"[\w\s\-',.!?:;()&/+#]{2,240}$", re.UNICODE)


def validate_topic(topic: str) -> str:
    text = (topic or "").strip()
    if len(text) < 2:
        raise ValidationError("Topic is too short.", stage="validate")
    if len(text) > 240:
        raise ValidationError("Topic must be 240 characters or fewer.", stage="validate")
    return text


def validate_aspect(aspect: str) -> str:
    value = (aspect or "9:16").strip()
    if value not in _ASPECTS:
        raise ValidationError(f"Unsupported aspect ratio: {aspect}", stage="validate")
    return value


def aspect_size(aspect: str, long_edge: int = 1920) -> tuple[int, int]:
    aspect = validate_aspect(aspect)
    mapping = {
        "9:16": (1080, 1920),
        "16:9": (1920, 1080),
        "1:1": (1080, 1080),
        "4:5": (1080, 1350),
        "21:9": (1920, 824),
    }
    return mapping[aspect]


def safe_filename(name: str, fallback: str = "video") -> str:
    cleaned = re.sub(r"[^\w\-. ]+", "", name or "", flags=re.UNICODE).strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    return (cleaned[:80] or fallback).lower()


def hex_color(value: str, default: str = "#FFFFFF") -> str:
    text = (value or default).strip()
    if re.fullmatch(r"#[0-9A-Fa-f]{6,8}", text):
        return text.upper()
    return default
