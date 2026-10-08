"""Script generation models."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Scene(BaseModel):
    narration: str
    search: str = ""
    visual: str = ""
    duration: float = Field(4.0, ge=1.0, le=180.0)
    start: float = 0.0
    end: float = 0.0

    @field_validator("search", mode="before")
    @classmethod
    def _search(cls, value: object) -> str:
        return str(value or "").strip()


class VideoScript(BaseModel):
    title: str
    description: str = ""
    hook: str = ""
    language: str = "en"
    template: str = "motivational"
    scenes: list[Scene] = Field(default_factory=list)
    raw_text: str = ""

    @property
    def narration(self) -> str:
        if self.raw_text.strip():
            return self.raw_text.strip()
        return " ".join(scene.narration.strip() for scene in self.scenes if scene.narration.strip())

    @property
    def search_terms(self) -> list[str]:
        terms: list[str] = []
        for scene in self.scenes:
            if scene.search:
                terms.append(scene.search)
        return terms

    def estimated_duration(self) -> float:
        if self.scenes:
            return float(sum(scene.duration for scene in self.scenes))
        words = len(self.narration.split())
        return max(8.0, words * 0.38)

    def apply_timings(self) -> None:
        cursor = 0.0
        for scene in self.scenes:
            scene.start = cursor
            scene.end = cursor + scene.duration
            cursor = scene.end


class ScriptRequest(BaseModel):
    topic: str
    language: str = "en"
    template: str = "motivational"
    duration: float = 30.0
    custom_script: Optional[str] = None
