"""Shared agent contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.models.video import VideoParams
from app.utils.logger import get_logger


ProgressFn = Callable[[int, str, str], None]


@dataclass
class AgentContext:
    task_id: str
    params: VideoParams
    workdir: Path
    payload: dict[str, Any] = field(default_factory=dict)
    report: ProgressFn | None = None

    def progress(self, value: int, stage: str, message: str = "") -> None:
        if self.report:
            self.report(value, stage, message)


@dataclass
class AgentResult:
    ok: bool = True
    stage: str = ""
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class BaseAgent(ABC):
    name = "agent"
    label = "Agent"
    start_progress = 0
    end_progress = 100
    optional = False

    def __init__(self) -> None:
        self.log = get_logger(self.name)

    @abstractmethod
    def run(self, ctx: AgentContext) -> AgentResult:
        raise NotImplementedError

    def fail(self, message: str) -> AgentResult:
        self.log.error("{} failed: {}", self.label, message)
        return AgentResult(ok=False, stage=self.name, message=message, error=message)
