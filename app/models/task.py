"""Task and job models."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models.video import VideoParams


class TaskState(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskCreate(BaseModel):
    params: VideoParams
    webhook_url: Optional[str] = None


class TaskRecord(BaseModel):
    task_id: str
    state: TaskState = TaskState.QUEUED
    progress: int = 0
    stage: str = "queued"
    message: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0
    params: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    logs: list[str] = Field(default_factory=list)

    def as_public(self) -> dict[str, Any]:
        return self.model_dump()
