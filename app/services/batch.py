"""Batch processing — one topic per line, many videos."""

from __future__ import annotations

from pathlib import Path

from app.models.video import VideoParams
from app.services import task as task_service
from app.utils.logger import get_logger

log = get_logger("batch")


def submit_topics(topics: list[str], base: VideoParams) -> list[str]:
    ids: list[str] = []
    for topic in topics:
        text = topic.strip()
        if not text or text.startswith("#"):
            continue
        params = base.model_copy(update={"topic": text})
        record = task_service.submit(params)
        ids.append(record.task_id)
        log.info("Queued batch item {} → {}", text, record.task_id)
    return ids


def submit_file(path: str | Path, base: VideoParams) -> list[str]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return submit_topics(lines, base)
