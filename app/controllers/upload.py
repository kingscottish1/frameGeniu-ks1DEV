"""Upload / publish endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.security.auth import AuthUser, require_auth
from app.security.db import get_db
from app.security.paths import safe_under
from app.services import upload as upload_service
from app.utils.exceptions import FrameGeniusError, ValidationError
from app.utils.file_manager import ROOT

router = APIRouter(prefix="/upload", tags=["upload"])


class PublishBody(BaseModel):
    video_path: str
    title: str
    description: str = ""
    platforms: list[str] = Field(default_factory=lambda: ["youtube"])
    tags: list[str] = Field(default_factory=list)


@router.post("")
def publish(body: PublishBody, user: AuthUser = Depends(require_auth)) -> dict:
    try:
        path = safe_under(body.video_path, ROOT / "outputs")
        receipt = upload_service.publish(
            path,
            title=body.title,
            description=body.description,
            platforms=body.platforms,
            tags=body.tags,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FrameGeniusError as exc:
        raise HTTPException(status_code=400, detail=exc.to_dict()) from exc
    get_db().audit("publish", user=user.username, detail=body.title[:80])
    return receipt
