"""Agent chat + image generation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.security.auth import AuthUser, require_auth
from app.security.paths import safe_under
from app.services import agent_chat
from app.services.imagine import extract_lettering, generate_image, images_dir, wants_lettering
from app.utils.exceptions import ValidationError
from app.utils.file_manager import ROOT
from app.utils.validators import safe_filename

router = APIRouter(prefix="/agent", tags=["agent"])


class ChatBody(BaseModel):
    message: str = Field("", max_length=12000)
    history: list[dict] = Field(default_factory=list)
    draw: bool = False
    provider: str | None = None
    model: str | None = None
    attachments: list[dict] = Field(default_factory=list)


class ImageBody(BaseModel):
    prompt: str = Field(..., min_length=2, max_length=2000)
    width: int = Field(1024, ge=256, le=1440)
    height: int = Field(1024, ge=256, le=1920)


@router.post("/chat")
def chat(body: ChatBody, user: AuthUser = Depends(require_auth)) -> dict:
    if not (body.message or "").strip() and not body.attachments:
        raise HTTPException(status_code=400, detail="Say something or attach a file.")
    return agent_chat.chat(
        body.message,
        history=body.history,
        draw=body.draw,
        provider=body.provider,
        model=body.model,
        attachments=body.attachments,
    )


@router.post("/image")
def image(body: ImageBody, user: AuthUser = Depends(require_auth)) -> dict:
    try:
        path = generate_image(
            body.prompt,
            width=body.width,
            height=body.height,
            allow_text=wants_lettering(body.prompt),
            lettering=extract_lettering(body.prompt),
            raw=True,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "ok": True,
        "prompt": body.prompt,
        "filename": path.name,
        "url": f"/api/v1/agent/images/{path.name}",
        "path": str(path),
    }


@router.post("/upload")
def upload(file: UploadFile = File(...), user: AuthUser = Depends(require_auth)) -> dict:
    raw = file.file.read()
    if not raw or len(raw) > 12 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File empty or too large (12 MB max).")
    name = safe_filename(file.filename or "upload", fallback="upload")
    ctype = (file.content_type or "").lower()
    suffix = ("" if "." not in name else name[name.rfind(".") :]).lower()
    image_ok = ctype.startswith("image/") or suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
    text_ok = ctype.startswith("text/") or suffix in {".txt", ".md", ".csv", ".json", ".log", ".py", ".html"}
    folder = images_dir()
    if image_ok:
        dest = folder / name
        dest.write_bytes(raw)
        return {
            "ok": True,
            "kind": "image",
            "filename": dest.name,
            "url": f"/api/v1/agent/images/{dest.name}",
            "text": "",
        }
    if text_ok:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1", errors="replace")
        return {
            "ok": True,
            "kind": "text",
            "filename": name,
            "url": "",
            "text": text[:20000],
        }
    raise HTTPException(status_code=400, detail="Use a picture or a text file.")


@router.get("/images/{name}")
def get_image(name: str, user: AuthUser = Depends(require_auth)):
    try:
        path = safe_under(images_dir() / name, ROOT / "outputs" / "images", ROOT / "outputs")
    except ValidationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    media = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return FileResponse(path, media_type=media, filename=path.name)
