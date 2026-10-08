"""Factory endpoints — trends, overnight batch, channel kit."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.models.video import VideoParams
from app.security.auth import AuthUser, require_auth
from app.security.db import get_db
from app.services import batch as batch_service
from app.services import channel as channel_service
from app.services import trends as trends_service

router = APIRouter(prefix="/factory", tags=["factory"])


class BatchBody(BaseModel):
    topics: list[str] = Field(..., min_length=1)
    template: str = "auto"
    language: str = "en"
    aspect_ratio: str = "9:16"
    duration: float = 30.0
    voice: str = "en-US-JennyNeural"
    llm_provider: str | None = "auto"
    ollama_model: str | None = None
    research_enabled: bool = True
    subtitle_enabled: bool = True
    bgm_enabled: bool = True
    cut_shorts: bool = True
    dual_export: bool = True
    hook_lock: bool = True
    series_name: str | None = None
    series_total: int | None = None


class ChannelBody(BaseModel):
    name: str | None = None
    handle: str | None = None
    voice: str | None = None
    watermark: bool | None = None
    intro_enabled: bool | None = None
    cta_enabled: bool | None = None
    cta_text: str | None = None


@router.get("/trends")
def trends(niche: str = "all", user: AuthUser = Depends(require_auth)) -> dict:
    items = trends_service.fetch_trends(niche=niche, limit=14)
    return {"items": items, "niche": niche}


@router.get("/channel")
def read_channel(user: AuthUser = Depends(require_auth)) -> dict:
    return channel_service.load_channel()


@router.put("/channel")
def write_channel(body: ChannelBody, user: AuthUser = Depends(require_auth)) -> dict:
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    saved = channel_service.save_channel(payload)
    get_db().audit("channel_update", user=user.username)
    return saved


@router.post("/batch")
def queue_batch(body: BatchBody, user: AuthUser = Depends(require_auth)) -> dict:
    topics = [t.strip() for t in body.topics if t and t.strip() and not t.strip().startswith("#")]
    if not topics:
        raise HTTPException(status_code=400, detail="Need at least one topic")
    if len(topics) > 20:
        raise HTTPException(status_code=400, detail="Max 20 topics a night")
    series = (body.series_name or "").strip()
    total = body.series_total or (len(topics) if series else None)
    ids: list[str] = []
    for index, topic in enumerate(topics, start=1):
        params = VideoParams(
            topic=topic,
            template=body.template or "auto",
            language=body.language,
            aspect_ratio=body.aspect_ratio,  # type: ignore[arg-type]
            duration=body.duration,
            voice=body.voice,
            llm_provider=body.llm_provider,
            ollama_model=body.ollama_model,
            research_enabled=body.research_enabled,
            subtitle_enabled=body.subtitle_enabled,
            bgm_enabled=body.bgm_enabled,
            cut_shorts=body.cut_shorts,
            dual_export=body.dual_export,
            hook_lock=body.hook_lock,
            series_name=series or None,
            series_part=index if series else None,
            series_total=total if series else None,
        )
        from app.services import task as task_service

        ids.append(task_service.submit(params).task_id)
    get_db().audit("factory_batch", user=user.username, detail=f"{len(ids)} topics")
    return {"ok": True, "count": len(ids), "task_ids": ids}
