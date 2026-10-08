"""Task management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.security.auth import AuthUser, require_auth
from app.security.db import get_db
from app.security.paths import is_safe_task_id
from app.services import task as task_service
from app.utils.exceptions import FrameGeniusError
from app.utils.progress import bus

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("")
def list_tasks(user: AuthUser = Depends(require_auth)) -> dict:
    return {"items": [item.as_public() for item in task_service.list_tasks()]}


@router.get("/{task_id}")
def get_task(task_id: str, user: AuthUser = Depends(require_auth)) -> dict:
    if not is_safe_task_id(task_id):
        raise HTTPException(status_code=400, detail="Bad task id")
    record = task_service.get_task(task_id)
    if not record:
        raise HTTPException(status_code=404, detail="Task not found")
    return record.as_public()


@router.post("/{task_id}/cancel")
def cancel_task(task_id: str, user: AuthUser = Depends(require_auth)) -> dict:
    try:
        record = task_service.cancel(task_id)
    except FrameGeniusError as exc:
        raise HTTPException(status_code=400, detail=exc.to_dict()) from exc
    get_db().audit("task_cancel", user=user.username, detail=task_id)
    return record.as_public()


@router.delete("/{task_id}")
def delete_task(task_id: str, user: AuthUser = Depends(require_auth)) -> dict:
    try:
        task_service.delete_task(task_id)
    except FrameGeniusError as exc:
        raise HTTPException(status_code=400, detail=exc.to_dict()) from exc
    get_db().audit("task_delete", user=user.username, detail=task_id)
    return {"ok": True, "task_id": task_id}


@router.get("/{task_id}/events")
async def task_events(task_id: str, user: AuthUser = Depends(require_auth)):
    import asyncio
    import json

    async def stream():
        last = None
        while True:
            snapshot = bus.snapshot(task_id)
            encoded = json.dumps(snapshot)
            if encoded != last:
                yield {"event": "progress", "data": encoded}
                last = encoded
            if snapshot.get("stage") in {"completed", "failed", "cancelled"}:
                break
            await asyncio.sleep(0.6)

    return EventSourceResponse(stream())
