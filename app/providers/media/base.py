"""Base stock-media interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MediaClip:
    path: Path
    duration: float
    source: str
    query: str = ""
    width: int = 0
    height: int = 0
    kind: str = "video"  # video | image


class BaseMediaProvider(ABC):
    name = "base"

    def __init__(self, **kwargs):
        self.options = kwargs

    @abstractmethod
    def search(self, query: str, *, orientation: str = "portrait", limit: int = 8) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def download(self, item: dict, dest: Path) -> MediaClip:
        raise NotImplementedError
