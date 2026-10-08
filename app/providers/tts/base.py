"""Base TTS interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TTSResult:
    path: Path
    duration: float
    words: list[dict] = field(default_factory=list)
    voice: str = ""
    provider: str = ""


class BaseTTS(ABC):
    name = "base"

    def __init__(self, **kwargs):
        self.options = kwargs

    @abstractmethod
    def synthesize(self, text: str, output: Path, *, voice: str, rate: str = "+0%", volume: str = "+0%", pitch: str = "+0Hz") -> TTSResult:
        raise NotImplementedError

    def list_voices(self) -> list[dict]:
        return []
