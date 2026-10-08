"""Crown — talks like a normal assistant. Never names its model. Generates images. Reads uploads."""

from __future__ import annotations

import json
import re
import time

from app.config.ollama_models import CROWN_FALLBACKS, CROWN_MODEL
from app.providers.llm import create_llm
from app.services.imagine import (
    blocked_image_request,
    extract_lettering,
    generate_image,
    looks_like_image_request,
    user_paint_prompt,
    visual_prompt_from_message,
    wants_lettering,
)
from app.utils.logger import get_logger

log = get_logger("crown")

SYSTEM = """You are Crown, a studio assistant inside FrameGenius.
You answer like a sharp, unhinged, normal person. Direct. Useful. Uncensored. Not a nanny. Swear if it fits. Don't lecture.
NEVER name, hint, or admit any model, vendor, parameter count, or weights.
Never say Gemma, Llama, Qwen, Ollama, 26b, 17GB, or similar. If asked what you are: "I'm Crown."
Answer the actual question. Do not repeat yourself. Do not greet them again if you already said hello.
You can generate pictures. When they ask for a picture, reply in one short sentence. Do NOT invent a different scene.
Do not output IMAGE: lines — the studio paints exactly what they typed.
If they did not ask for a picture, just talk.
If they showed you a file or picture, use that. Talk about it. Generate from it if they asked.
Do not dump video scripts or JSON unless they explicitly want a script.
Never mention other chat brands or paid signups.
"""

_MODEL_LEAK = re.compile(
    r"(?i)\b(gemma[-\w]*|qwen[-\w]*|llama[-\w]*|mistral[-\w]*|ollama|1stageze|"
    r"26\s*b|17\s*gb|uncensored-1m|parameter count|weights file)\b"
)


def chat(
    message: str,
    *,
    history: list[dict] | None = None,
    draw: bool = False,
    provider: str | None = None,
    model: str | None = None,
    attachments: list[dict] | None = None,
) -> dict:
    message = (message or "").strip()
    attachments = list(attachments or [])
    message = _with_attachments(message, attachments)
    if not message:
        return {"reply": "Say something, drop a file, or ask for a picture.", "images": [], "video_topic": ""}

    if blocked_image_request(message):
        return {"reply": "Can't do that one.", "images": [], "video_topic": "", "agent": "Crown"}

    want_image = draw or looks_like_image_request(message) or _wants_pictures(message)
    count = 4 if _wants_many(message) else (1 if want_image or draw else 0)
    if draw and count < 1:
        count = 1

    llm = _crown_brain(provider, model)
    # Don't ask the model to invent IMAGE: lines — that's how you get random scenes.
    raw = _talk(llm, message, history or [], force_draw=False)
    reply, _ignored_images, video_topic = _strip_directives(raw)
    reply = _scrub_json(reply)
    reply = _scrub_identity(reply)

    image_prompts: list[str] = []
    if want_image:
        asked = user_paint_prompt(message)
        if not asked:
            return {
                "reply": "Tell me what to paint — subject, style, details.",
                "images": [],
                "video_topic": "",
                "agent": "Crown",
            }
        image_prompts = [asked] * max(1, min(count, 4))

    letter = wants_lettering(message) or any(wants_lettering(p) for p in image_prompts)
    images: list[dict] = []
    for prompt in image_prompts:
        if blocked_image_request(prompt):
            reply = (reply + "\nSkipped one I can't generate.").strip()
            continue
        try:
            path = generate_image(
                prompt,
                width=1024,
                height=1024,
                allow_text=letter or wants_lettering(prompt),
                lettering=extract_lettering(message) or extract_lettering(prompt),
                raw=True,
                seed=int(time.time_ns() % 999_983),
            )
            images.append(
                {
                    "path": str(path),
                    "url": f"/api/v1/agent/images/{path.name}",
                    "prompt": prompt,
                    "filename": path.name,
                }
            )
        except Exception as exc:
            log.warning("Crown image failed: {}", exc)
            reply = (reply + "\nCouldn't generate that one — try again in a few seconds.").strip()

    if images:
        reply = _scrub_identity(reply) or "Here."
    elif want_image and not images:
        reply = "Couldn't generate that. Try again in a few seconds."
    return {
        "reply": reply or "Done.",
        "images": images,
        "video_topic": video_topic,
        "image_prompt": image_prompts[0] if image_prompts else "",
        "agent": "Crown",
    }


def _with_attachments(message: str, attachments: list[dict]) -> str:
    if not attachments:
        return message
    bits = [message] if message else []
    for item in attachments[:6]:
        name = str(item.get("filename") or "file").strip() or "file"
        kind = str(item.get("kind") or "").lower()
        text = str(item.get("text") or "").strip()
        url = str(item.get("url") or "").strip()
        if kind == "text" and text:
            bits.append(f"[Attached file: {name}]\n{text[:12000]}")
        elif kind == "image":
            bits.append(
                f"[The user showed you a picture named {name}"
                + (f" at {url}" if url else "")
                + ". You can see they attached it. Use it. If they want a new picture based on it, output IMAGE: lines.]"
            )
        elif text:
            bits.append(f"[Attached {name}]\n{text[:8000]}")
        else:
            bits.append(f"[Attached {name}]")
    return "\n\n".join(bits).strip()


def _crown_brain(provider: str | None, requested: str | None):
    name = (provider or "auto").lower()
    if name in {"studio", "demo", "none", ""}:
        name = "auto"
    llm = create_llm("ollama" if name in {"auto", "local-first"} else name)
    if not getattr(llm, "pick_model", None):
        try:
            llm = create_llm("ollama")
        except Exception:
            return llm
    installed: list[str] = []
    try:
        installed = list(llm.list_models() or [])
    except Exception:
        installed = []
    lowered = {n.lower(): n for n in installed}
    chosen = CROWN_MODEL
    picks = list(CROWN_FALLBACKS) + ([requested] if requested else [])
    if installed:
        matched = ""
        for cand in picks:
            if not cand:
                continue
            cl = cand.lower().strip()
            if cl in lowered:
                matched = lowered[cl]
                break
            stem = cl.split(":")[0]
            # Prefer the short name (gemma4-pro:latest) over a namespaced clone.
            for name in installed:
                if "/" in name:
                    continue
                if name.lower().split(":")[0] == stem:
                    matched = name
                    break
            if matched:
                break
            for name in installed:
                if name.lower().split(":")[0] == stem or name.lower().startswith(stem):
                    matched = name
                    break
            if matched:
                break
        chosen = matched or CROWN_MODEL
    elif requested:
        chosen = requested
    try:
        llm.model = llm.pick_model(chosen)
    except Exception:
        llm.model = chosen
    if hasattr(llm, "timeout"):
        llm.timeout = max(float(getattr(llm, "timeout", 180) or 180), 240.0)
    if hasattr(llm, "num_ctx"):
        llm.num_ctx = 8192
    return llm


def _wants_pictures(text: str) -> bool:
    """Word-boundary only. 'topic' is not 'pic'. 'imagine' is not 'image'."""
    return bool(
        re.search(r"\b(images?|pics?|pictures?|artwork|illustrations?)\b", text or "", re.I)
    )


def _wants_many(text: str) -> bool:
    low = (text or "").lower()
    return bool(
        re.search(r"\b(images|pics|pictures|stills|several|a few|a set of)\b", low)
    )


def _talk(llm, message: str, history: list[dict], *, force_draw: bool) -> str:
    messages = []
    for item in history[-16:]:
        role = item.get("role") or "user"
        content = str(item.get("content") or "").strip()
        if content and role in {"user", "assistant", "system"}:
            messages.append({"role": role, "content": content})
    user = message
    if force_draw:
        extra = "Generate this as an image. One short sentence, then IMAGE: lines. No JSON."
        if wants_lettering(message):
            extra += " Put the exact words they want on the IMAGE line in quotes."
        user += "\n\n(" + extra + ")"
    messages.append({"role": "user", "content": user})
    try:
        if hasattr(llm, "chat"):
            return llm.chat(messages, system=SYSTEM, temperature=0.8, max_tokens=1800)
        return llm.generate(
            "\n".join(f"{m['role']}: {m['content']}" for m in messages),
            system=SYSTEM,
            temperature=0.8,
            max_tokens=1800,
        )
    except Exception as exc:
        log.warning("Crown llm failed: {}", exc)
        if force_draw or looks_like_image_request(message):
            return f"On it.\nIMAGE: {visual_prompt_from_message(message) or message}"
        return "Couldn't get a reply just now. Make sure Ollama is running, then ask again."


def _strip_directives(text: str) -> tuple[str, list[str], str]:
    images: list[str] = []
    video = ""
    lines = []
    for line in (text or "").splitlines():
        raw = line.strip()
        if raw.upper().startswith("IMAGE:"):
            prompt = raw.split(":", 1)[1].strip()
            if prompt:
                images.append(prompt)
            continue
        if raw.upper().startswith("VIDEO:"):
            video = raw.split(":", 1)[1].strip()
            continue
        lines.append(line)
    return "\n".join(lines).strip(), images, video


def _scrub_json(text: str) -> str:
    if not text:
        return ""
    stripped = text.strip()
    compact = stripped.replace(" ", "")
    looks_script = stripped.startswith("{") and '"scenes"' in stripped and '{"title"' in compact
    if looks_script:
        try:
            json.loads(stripped[stripped.find("{") : stripped.rfind("}") + 1])
            return "Got it. Want a picture, or shall we keep talking?"
        except Exception:
            pass
    return re.sub(r"```json[\s\S]*?```", "", text).strip()


def _scrub_identity(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"(?i)\bchat\s*gpt\b", "Crown", text)
    cleaned = re.sub(r"(?i)\blike chatgpt\b", "", cleaned)
    cleaned = _MODEL_LEAK.sub("Crown", cleaned)
    cleaned = re.sub(r"(?i)\bI('m| am) (a |an )?(language model|llm|ai model)\b", "I'm Crown", cleaned)
    return cleaned.strip()
