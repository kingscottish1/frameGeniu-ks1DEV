"""Task orchestration — hands work to the multi-agent conductor."""

from __future__ import annotations

import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.agents.orchestrator import run_crew
from app.config.settings import get_settings
from app.models.task import TaskRecord, TaskState
from app.models.video import VideoParams
from app.utils.exceptions import TaskError
from app.utils.logger import get_logger
from app.utils.progress import bus

log = get_logger("task")

_LOCK = threading.RLock()
_TASKS: dict[str, TaskRecord] = {}
_EXECUTOR: ThreadPoolExecutor | None = None
_FUTURES: dict[str, Any] = {}
_LOADED = False


def _executor() -> ThreadPoolExecutor:
    global _EXECUTOR
    if _EXECUTOR is None:
        workers = int(get_settings().app.get("max_concurrent_tasks") or 2)
        _EXECUTOR = ThreadPoolExecutor(max_workers=max(1, workers), thread_name_prefix="fg-task")
    return _EXECUTOR


def _state_path():
    path = get_settings().files.output_dir / "state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _persist() -> None:
    payload = {key: record.model_dump() for key, record in _TASKS.items()}
    path = _state_path()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        import os

        os.chmod(path, 0o600)
    except OSError:
        pass
    try:
        from app.security.db import get_db

        db = get_db()
        for record in _TASKS.values():
            db.upsert_task(record.model_dump())
        db.flush()
    except Exception as exc:
        log.warning("encrypted task persist skipped: {}", exc)


def _load() -> None:
    try:
        from app.security.crypto import ensure_master_key
        from app.security.db import get_db

        ensure_master_key()
        rows = get_db().load_tasks()
        for value in rows:
            try:
                _TASKS[value["task_id"]] = TaskRecord.model_validate(value)
            except Exception:
                continue
        if _TASKS:
            return
    except Exception as exc:
        log.warning("encrypted task load skipped: {}", exc)
    path = _state_path()
    if not path.exists():
        return
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    for key, value in raw.items():
        try:
            _TASKS[key] = TaskRecord.model_validate(value)
        except Exception:
            continue


def _ensure_loaded() -> None:
    global _LOADED
    if _LOADED:
        return
    _load()
    _LOADED = True


def _touch(task_id: str, **fields: Any) -> TaskRecord:
    with _LOCK:
        record = _TASKS[task_id]
        data = record.model_dump()
        data.update(fields)
        data["updated_at"] = time.time()
        record = TaskRecord.model_validate(data)
        _TASKS[task_id] = record
        _persist()
        return record


def submit(params: VideoParams) -> TaskRecord:
    _ensure_loaded()
    try:
        from app.services.channel import apply_channel

        params = apply_channel(params)
    except Exception:
        pass
    settings = get_settings()
    queued = [item for item in _TASKS.values() if item.state in {TaskState.QUEUED, TaskState.PROCESSING}]
    max_queued = int(settings.app.get("max_queued_tasks") or 20)
    if len(queued) >= max_queued:
        raise TaskError("Too many queued tasks. Wait for a render to finish.", stage="queue")

    task_id = uuid.uuid4().hex[:12]
    now = time.time()
    record = TaskRecord(
        task_id=task_id,
        state=TaskState.QUEUED,
        progress=0,
        stage="queued",
        created_at=now,
        updated_at=now,
        params=params.model_dump(),
    )
    with _LOCK:
        _TASKS[task_id] = record
        _persist()
    future = _executor().submit(_run, task_id, params)
    _FUTURES[task_id] = future
    return record


def get_task(task_id: str) -> TaskRecord | None:
    _ensure_loaded()
    return _TASKS.get(task_id)


def list_tasks() -> list[TaskRecord]:
    _ensure_loaded()
    return sorted(_TASKS.values(), key=lambda item: item.created_at, reverse=True)


def cancel(task_id: str) -> TaskRecord:
    record = get_task(task_id)
    if not record:
        raise TaskError("Task not found.", stage="cancel")
    future = _FUTURES.get(task_id)
    if future and not future.done():
        future.cancel()
    return _touch(task_id, state=TaskState.CANCELLED, stage="cancelled", message="Cancelled by user")


def delete_task(task_id: str) -> None:
    record = get_task(task_id)
    if not record:
        return
    if record.state == TaskState.PROCESSING:
        raise TaskError("Cannot delete a task that is still rendering.", stage="delete")
    with _LOCK:
        _TASKS.pop(task_id, None)
        _persist()
    try:
        from app.security.db import get_db

        get_db().delete_task(task_id)
        get_db().flush()
    except Exception:
        pass
    work = get_settings().files.task_dir(task_id)
    if work.exists():
        import shutil

        shutil.rmtree(work, ignore_errors=True)


def run_sync(params: VideoParams, task_id: str | None = None) -> TaskRecord:
    _ensure_loaded()
    task_id = task_id or uuid.uuid4().hex[:12]
    now = time.time()
    record = TaskRecord(
        task_id=task_id,
        state=TaskState.QUEUED,
        created_at=now,
        updated_at=now,
        params=params.model_dump(),
    )
    with _LOCK:
        _TASKS[task_id] = record
        _persist()
    return _run(task_id, params)


def _progress(task_id: str, value: int, stage: str, message: str = "") -> None:
    _touch(task_id, progress=value, stage=stage, message=message, state=TaskState.PROCESSING)
    bus.update(task_id, value, stage, message=message)
    log.info("[{}] {:>3}% {}", task_id, value, stage)


def _run(task_id: str, params: VideoParams) -> TaskRecord:
    settings = get_settings()
    workdir = settings.files.task_dir(task_id)
    try:
        result = run_crew(
            task_id,
            params,
            workdir,
            report=lambda value, stage, message="": _progress(task_id, value, stage, message),
        )
        record = _touch(
            task_id,
            state=TaskState.COMPLETED,
            progress=100,
            stage="completed",
            message="Ready",
            result=result,
            error=None,
        )
        bus.update(task_id, 100, "completed", message="Ready")
        _fire_webhook("on_complete", record)
        return record
    except Exception as exc:
        log.exception("Task {} failed", task_id)
        record = _touch(
            task_id,
            state=TaskState.FAILED,
            stage="failed",
            message=str(exc),
            error=str(exc),
        )
        bus.update(task_id, record.progress, "failed", message=str(exc))
        _fire_webhook("on_failed", record)
        return record


def _fire_webhook(event: str, record: TaskRecord) -> None:
    settings = get_settings()
    hooks = settings.section("webhooks")
    if not hooks.get("enabled"):
        return
    url = str(hooks.get(event) or "")
    if not url:
        return
    try:
        import httpx

        httpx.post(url, json=record.as_public(), timeout=8)
    except Exception as exc:
        log.warning("Webhook {} failed: {}", event, exc)
