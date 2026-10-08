"""Video configuration models."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AspectRatio(str, Enum):
    PORTRAIT = "9:16"
    LANDSCAPE = "16:9"
    SQUARE = "1:1"
    TALL = "4:5"
    ULTRAWIDE = "21:9"


class VideoParams(BaseModel):
    topic: str = Field(..., min_length=2, max_length=240)
    script_text: Optional[str] = None
    template: str = "motivational"
    language: str = "en"
    aspect_ratio: AspectRatio = AspectRatio.PORTRAIT
    duration: float = Field(30.0, ge=8.0, le=1800.0)
    voice: str = "en-GB-LibbyNeural"
    tts_provider: Optional[str] = None
    llm_provider: Optional[str] = None
    ollama_model: Optional[str] = None
    media_provider: Optional[str] = None
    research_enabled: bool = True
    subtitle_enabled: bool = True
    bgm_enabled: bool = True
    bgm_path: Optional[str] = None
    color_grade: str = "cinematic"
    transition: str = "fade"
    concat_mode: str = "sequential"
    watermark: bool = True
    intro_enabled: bool = True
    cta_enabled: bool = True
    cut_shorts: bool = True
    dual_export: bool = True
    hook_lock: bool = True
    series_name: Optional[str] = None
    series_part: Optional[int] = Field(default=None, ge=1, le=99)
    series_total: Optional[int] = Field(default=None, ge=1, le=99)
    extra_keywords: list[str] = Field(default_factory=list)
    source_video: Optional[str] = None
    bleep_profanity: bool = True

    def size(self) -> tuple[int, int]:
        return {
            AspectRatio.PORTRAIT: (1080, 1920),
            AspectRatio.LANDSCAPE: (1920, 1080),
            AspectRatio.SQUARE: (1080, 1080),
            AspectRatio.TALL: (1080, 1350),
            AspectRatio.ULTRAWIDE: (1920, 824),
        }[self.aspect_ratio]


class VideoResult(BaseModel):
    task_id: str
    video_path: str
    thumbnail_path: Optional[str] = None
    script_path: Optional[str] = None
    subtitle_path: Optional[str] = None
    duration: float = 0.0
    title: str = ""
