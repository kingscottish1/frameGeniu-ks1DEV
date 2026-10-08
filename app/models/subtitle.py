"""Subtitle models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SubtitleCue(BaseModel):
    index: int
    start: float
    end: float
    text: str
    words: list[str] = Field(default_factory=list)


class SubtitleTrack(BaseModel):
    cues: list[SubtitleCue] = Field(default_factory=list)
    srt_path: str = ""
    ass_path: str = ""
    language: str = "en"

    def to_srt(self) -> str:
        blocks: list[str] = []
        for cue in self.cues:
            blocks.append(
                f"{cue.index}\n{_ts(cue.start)} --> {_ts(cue.end)}\n{cue.text.strip()}\n"
            )
        return "\n".join(blocks).strip() + "\n"


def _ts(seconds: float) -> str:
    millis = int(round(max(0.0, seconds) * 1000))
    hours, rem = divmod(millis, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"
