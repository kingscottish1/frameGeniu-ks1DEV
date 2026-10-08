"""Conductor — runs the FrameGenius crew in order."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from app.agents.base import AgentContext, AgentResult, BaseAgent, ProgressFn
from app.agents.backgrounds import BackgroundsAgent
from app.agents.caption import CaptionAgent
from app.agents.clean import AudioCleanAgent
from app.agents.editor import EditorAgent
from app.agents.media import MediaScoutAgent
from app.agents.publisher import PublisherAgent
from app.agents.research import ResearchAgent
from app.agents.text import TextAgent
from app.agents.voice import VoiceAgent
from app.agents.writer import WriterAgent
from app.models.video import VideoParams
from app.utils.exceptions import TaskError
from app.utils.logger import get_logger

log = get_logger("conductor")

DEFAULT_CREW: tuple[type[BaseAgent], ...] = (
    ResearchAgent,
    WriterAgent,
    TextAgent,
    VoiceAgent,
    BackgroundsAgent,
    MediaScoutAgent,
    CaptionAgent,
    EditorAgent,
    PublisherAgent,
)

# Uploaded film: keep the (bleeped) sound, paint new pictures.
RESKIN_CREW: tuple[type[BaseAgent], ...] = (
    AudioCleanAgent,
    BackgroundsAgent,
    MediaScoutAgent,
    CaptionAgent,
    EditorAgent,
    PublisherAgent,
)


class Conductor:
    def __init__(self, crew: Sequence[type[BaseAgent]] | None = None) -> None:
        self.crew = [cls() for cls in (crew or DEFAULT_CREW)]

    def run(
        self,
        *,
        task_id: str,
        params: VideoParams,
        workdir: Path,
        report: ProgressFn | None = None,
    ) -> dict:
        ctx = AgentContext(task_id=task_id, params=params, workdir=workdir, report=report)
        workdir.mkdir(parents=True, exist_ok=True)
        log.info("Conductor starting {} with {} agents", task_id, len(self.crew))
        for agent in self.crew:
            optional = bool(getattr(agent, "optional", False))
            try:
                result: AgentResult = agent.run(ctx)
            except Exception as exc:
                if optional:
                    log.warning("[{}] optional {} crashed ({}) — continuing", task_id, agent.label, exc)
                    continue
                raise
            if not result.ok:
                if optional:
                    log.warning(
                        "[{}] optional {} failed ({}) — continuing",
                        task_id,
                        agent.label,
                        result.error or result.message,
                    )
                    continue
                raise TaskError(result.error or f"{agent.label} failed", stage=agent.name)
            log.info("[{}] {} ok — {}", task_id, agent.label, result.message or result.stage)
        return ctx.payload.get("result") or {}


def run_crew(task_id: str, params: VideoParams, workdir: Path, report: ProgressFn | None = None) -> dict:
    if str(getattr(params, "source_video", "") or "").strip():
        return Conductor(RESKIN_CREW).run(task_id=task_id, params=params, workdir=workdir, report=report)
    return Conductor().run(task_id=task_id, params=params, workdir=workdir, report=report)
