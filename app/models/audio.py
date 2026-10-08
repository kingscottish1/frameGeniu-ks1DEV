"""Audio / TTS models."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class VoiceInfo(BaseModel):
    id: str
    name: str
    locale: str = "en-US"
    gender: str = "female"
    provider: str = "edge"
    preview: Optional[str] = None


class WordTiming(BaseModel):
    word: str
    start: float
    end: float


class AudioParams(BaseModel):
    text: str
    voice: str = "en-US-JennyNeural"
    provider: str = "edge"
    rate: str = "+0%"
    volume: str = "+0%"
    pitch: str = "+0Hz"


class AudioResult(BaseModel):
    path: str
    duration: float
    words: list[WordTiming] = []
    voice: str = ""
    provider: str = ""
