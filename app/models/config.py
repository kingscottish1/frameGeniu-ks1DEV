"""Configuration update payload."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ConfigUpdate(BaseModel):
    app: Optional[dict[str, Any]] = None
    llm: Optional[dict[str, Any]] = None
    tts: Optional[dict[str, Any]] = None
    media: Optional[dict[str, Any]] = None
    video: Optional[dict[str, Any]] = None
    subtitle: Optional[dict[str, Any]] = None
    audio: Optional[dict[str, Any]] = None
    whisper: Optional[dict[str, Any]] = None
    upload: Optional[dict[str, Any]] = None
    ui: Optional[dict[str, Any]] = None
    proxy: Optional[dict[str, Any]] = None
    webhooks: Optional[dict[str, Any]] = None
    channel: Optional[dict[str, Any]] = None

    def sections(self) -> dict[str, dict[str, Any]]:
        payload = self.model_dump(exclude_none=True)
        return {key: value for key, value in payload.items() if isinstance(value, dict)}


class HealthStatus(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    author: str = "kingscottishDEV N.A.S"
    ffmpeg: bool = False
    demo_mode: bool = True
    providers: dict[str, str] = Field(default_factory=dict)
