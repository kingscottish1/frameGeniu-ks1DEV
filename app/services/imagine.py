"""Generate any image from a prompt. Free, no signup, no API key.

Film stills stay photoreal. Crown sends the prompt as asked.
Never returns a text poster. If every model fails, it raises.
"""

from __future__ import annotations

import hashlib
import re
import threading
import time
from pathlib import Path
from urllib.parse import quote

import httpx

from app.config.settings import get_settings
from app.utils.logger import get_logger
from app.utils.validators import safe_filename

log = get_logger("imagine")

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": BROWSER_UA,
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Referer": "https://pollinations.ai/",
    "Accept-Language": "en-GB,en;q=0.9",
}

_NO_TEXT = (
    "photoreal 35mm documentary photograph, natural lighting, sharp focus, film grain, "
    "not CGI, not digital art, not illustration, "
    "no text, no letters, no words, no typography, no title card, "
    "no watermark, no logo, no caption, no poster, no subtitles"
)

_LOCK = threading.Lock()
_LAST_CALL = 0.0
# Anonymous Pollinations is ~1 image / 15s. Going faster returns 429 or empty JPEGs.
_GAP = 16.0


def images_dir() -> Path:
    folder = get_settings().files.output_dir / "images"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def wants_lettering(text: str) -> bool:
    """True when they asked for words ON the picture. Word-boundaries only — 'context' is not 'text'."""
    low = (text or "").lower()
    return bool(
        re.search(
            r"\b(text|words?|says|quote|title|caption|letters?|typography|"
            r"headline|lettering|sign|write on|put (the )?words|with text|add text)\b",
            low,
        )
    )


def extract_lettering(text: str) -> str:
    """Pull the exact words they want burned onto the picture."""
    raw = (text or "").strip()
    if not raw:
        return ""
    for pattern in (
        r"[“\"]([^\"“”]{1,90})[”\"]",
        r"'([^']{2,80})'",
        r"(?i)(?:with (?:the )?(?:words?|text|title)|that says?|reading|text:|title:|caption:|write)\s+['“\"]?([^'\"\n]{2,80})",
    ):
        match = re.search(pattern, raw)
        if match:
            phrase = (match.group(1) or "").strip(" \t\"'")
            if 1 < len(phrase) <= 90:
                return phrase
    return ""


def photoreal_prompt(prompt: str, *, allow_text: bool | None = None) -> str:
    """Film-still look. Crown does not use this — it sends the user's prompt as-is."""
    base = visual_prompt_from_message(prompt)
    base = re.sub(r"\s+", " ", base).strip(" .,:;")
    if allow_text is None:
        allow_text = wants_lettering(prompt)
    if allow_text:
        return f"{base}, cinematic, sharp, include the requested text in the image, legible lettering"[:420]
    if "no text" in base.lower() and "photoreal" in base.lower():
        return base[:420]
    return f"{base}, {_NO_TEXT}"[:420]


def image_prompt(prompt: str) -> str:
    """Whatever they asked for. Any style. No forced photoreal, no 'no text' gag."""
    base = visual_prompt_from_message(prompt)
    return re.sub(r"\s+", " ", base).strip(" .,:;")[:800]


_BLOCKED = re.compile(
    r"\b(loli|shota|lolicon|shotacon|child\s*porn|child\s*sex|preteen|"
    r"underage\s*(girl|boy|sex|nude)|pedo|paedo|minor\s*(nude|sex)|kid\s*porn)\b",
    re.I,
)


def blocked_image_request(text: str) -> bool:
    return bool(_BLOCKED.search(text or ""))


def generate_image(
    prompt: str,
    *,
    width: int = 1024,
    height: int = 1024,
    dest: Path | None = None,
    seed: int | None = None,
    allow_text: bool | None = None,
    lettering: str = "",
    raw: bool = False,
) -> Path:
    source = prompt or ""
    if blocked_image_request(source):
        raise ValueError("Can't generate that.")
    if allow_text is None:
        allow_text = wants_lettering(source)
    words = (lettering or extract_lettering(source)).strip()
    if words:
        allow_text = True
    painted = image_prompt(source) if raw else photoreal_prompt(source, allow_text=allow_text)
    if len(painted) < 2:
        raise ValueError("Describe the image you want.")
    slug = safe_filename(painted[:48], fallback="image")
    digest = hashlib.sha1(painted.encode("utf-8")).hexdigest()[:8]
    dest = Path(dest) if dest else images_dir() / f"{slug}_{digest}.jpg"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if seed is None:
        seed = int(hashlib.sha1(f"{dest}:{painted}".encode()).hexdigest()[:8], 16) % 999_983

    errors: list[str] = []
    gw, gh = _gen_size(width, height)
    for attempt in range(4):
        try:
            if _from_pollinations(painted, gw, gh, dest, seed + attempt, nsfw=bool(raw)):
                _fit_image(dest, width, height)
                if words:
                    _stamp_lettering(dest, words)
                return dest
        except Exception as exc:
            errors.append(f"pollinations:{exc}")
            log.warning("pollinations attempt {} failed: {}", attempt + 1, exc)
            time.sleep(3 + attempt * 5)

    try:
        if _from_horde(painted, gw, gh, dest, seed, nsfw=bool(raw)):
            _fit_image(dest, width, height)
            if words:
                _stamp_lettering(dest, words)
            return dest
    except Exception as exc:
        errors.append(f"horde:{exc}")
        log.warning("horde image failed: {}", exc)

    if dest.exists():
        dest.unlink(missing_ok=True)
    raise RuntimeError("Could not generate that image. " + " | ".join(errors[:3]))


def looks_like_image_request(text: str) -> bool:
    low = (text or "").lower()
    triggers = (
        "draw ", "draw me", "generate an image", "generate a picture", "generate a pic",
        "generate me", "gen an image", "gen a pic", "make an image", "make a picture",
        "make a pic", "make me an", "make me a", "create an image", "create a picture", "paint ",
        "picture of", "image of", "photo of", "render an", "imagine ",
        "show me a picture", "show me an image", "paint this", "an image of",
        "a picture of", "artwork of", "illustration of", "i want a pic", "i want a picture",
        "i want an image", "can you draw", "can you paint", "do a picture", "do an image",
    )
    return any(item in low for item in triggers)


def visual_prompt_from_message(text: str) -> str:
    text = (text or "").strip()
    cleaned = re.sub(
        r"(?i)^(please\s+)?(can you\s+|could you\s+)?(draw|paint|generate|create|make|render|imagine|show me)\s+"
        r"(me\s+)?(an?\s+)?(image|picture|pic|photo|illustration|art)?\s*(of|showing)?\s*",
        "",
        text,
    ).strip(" .,:;")
    cleaned = re.sub(r"(?i)^(an?\s+)?(image|picture|pic|photo)\s+(of|showing)\s+", "", cleaned).strip(" .,:;")
    return cleaned or text


def user_paint_prompt(message: str) -> str:
    """Duck.ai style: the user's scene, their style, their details. Nothing extra."""
    text = (message or "").strip()
    text = re.sub(r"\[The user showed you.*?\]", " ", text, flags=re.I | re.S)
    text = re.sub(r"\[Attached(?: file)?:[^\]]*\]", " ", text, flags=re.I)
    text = visual_prompt_from_message(text)
    text = re.sub(r"\s+", " ", text).strip(" .,:;")
    if text.lower() in {"a picture", "picture", "an image", "image", "a pic", "pic", "pics", "photos", "photo"}:
        return ""
    return text[:800]


def _pace() -> None:
    global _LAST_CALL
    with _LOCK:
        now = time.time()
        wait = _GAP - (now - _LAST_CALL)
        if wait > 0:
            time.sleep(wait)
        _LAST_CALL = time.time()


def _gen_size(width: int, height: int) -> tuple[int, int]:
    """Keep requests inside sizes Pollinations actually paints."""
    width = max(512, int(width or 1024))
    height = max(512, int(height or 1024))
    cap = 1280
    if max(width, height) > cap:
        scale = cap / float(max(width, height))
        width = int(width * scale)
        height = int(height * scale)
    width = max(512, min(1280, (width // 8) * 8))
    height = max(512, min(1280, (height // 8) * 8))
    return width, height


def _fit_image(path: Path, width: int, height: int) -> None:
    if width < 32 or height < 32:
        return
    try:
        from PIL import Image
    except Exception:
        return
    try:
        im = Image.open(path).convert("RGB")
    except Exception:
        return
    if im.size == (width, height):
        return
    try:
        resample = Image.Resampling.LANCZOS
    except Exception:
        resample = Image.BICUBIC
    im = im.resize((width, height), resample)
    im.save(path, "JPEG", quality=90)


def _from_pollinations(prompt: str, width: int, height: int, dest: Path, seed: int, nsfw: bool = False) -> bool:
    """Free Flux via image.pollinations.ai — no signup, no key."""
    encoded = quote(prompt[:800])
    models = ("flux", "", "turbo")
    timeout = httpx.Timeout(25.0, read=90.0)
    for model in models:
        qs = f"width={width}&height={height}&nologo=true&seed={seed}"
        if model:
            qs += f"&model={model}"
        if nsfw:
            qs += "&safe=false"
        url = f"https://image.pollinations.ai/prompt/{encoded}?{qs}"
        _pace()
        try:
            with httpx.Client(headers=HEADERS, timeout=timeout, follow_redirects=True) as client:
                resp = client.get(url)
            if resp.status_code == 429:
                log.warning("Pollinations rate-limited, waiting 18s")
                time.sleep(18)
                continue
            if resp.status_code >= 400:
                log.warning("Pollinations {} {}", model or "default", resp.status_code)
                continue
            data = resp.content or b""
            if not _is_real_image(data[:16], len(data)):
                log.warning("Pollinations {} returned no image ({} bytes)", model or "default", len(data))
                continue
            dest.write_bytes(data)
            log.info("Painted {} ({} bytes) via pollinations {}", dest.name, len(data), model or "flux")
            return True
        except Exception as exc:
            log.warning("pollinations {} failed: {}", model or "default", exc)
    return False


def _from_horde(prompt: str, width: int, height: int, dest: Path, seed: int, nsfw: bool = False) -> bool:
    """AI Horde — free distributed Stable Diffusion, anonymous, no signup."""
    w = max(512, min(1024, (int(width) // 64) * 64))
    h = max(512, min(1024, (int(height) // 64) * 64))
    headers = {
        "apikey": "0000000000",
        "Client-Agent": "FrameGenius:1.10.2:kingscottishDEV",
        "Content-Type": "application/json",
    }
    if nsfw:
        horde_prompt = prompt
    elif wants_lettering(prompt):
        horde_prompt = f"{prompt} ### watermark, logo"
    else:
        horde_prompt = f"{prompt} ### text, letters, watermark, logo, title card"
    body = {
        "prompt": horde_prompt,
        "params": {
            "sampler_name": "k_euler",
            "cfg_scale": 7.0,
            "width": w,
            "height": h,
            "steps": 20,
            "n": 1,
            "seed": str(seed),
        },
        "nsfw": bool(nsfw),
        "censor_nsfw": not nsfw,
        "r2": True,
        "trusted_workers": False,
        "models": ["FLUX.1-schnell", "AlbedoBase XL (SDXL)", "stable_diffusion"],
    }
    timeout = httpx.Timeout(20.0, read=40.0)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        started = None
        for host in ("https://aihorde.net", "https://stablehorde.net"):
            try:
                resp = client.post(f"{host}/api/v2/generate/async", headers=headers, json=body)
                if resp.status_code >= 400:
                    log.warning("horde {} {}", host, resp.status_code)
                    continue
                started = resp.json()
                base = host
                break
            except Exception as exc:
                log.warning("horde submit {}: {}", host, exc)
        if not started or not started.get("id"):
            return False
        job = started["id"]
        deadline = time.time() + 95
        while time.time() < deadline:
            time.sleep(3.5)
            check = client.get(f"{base}/api/v2/generate/check/{job}", headers=headers)
            if check.status_code >= 400:
                continue
            info = check.json()
            if info.get("done") or info.get("faulted"):
                break
        status = client.get(f"{base}/api/v2/generate/status/{job}", headers=headers)
        status.raise_for_status()
        gens = (status.json() or {}).get("generations") or []
        if not gens:
            return False
        img = gens[0].get("img") or ""
        if not img:
            return False
        if img.startswith("http"):
            data = client.get(img).content
        else:
            import base64

            data = base64.b64decode(img)
        if not _is_real_image(data[:16], len(data)):
            return False
        dest.write_bytes(data)
        log.info("Painted {} ({} bytes) via horde", dest.name, len(data))
        return True


def _stamp_lettering(path: Path, text: str) -> None:
    """Burn readable words onto the picture. Flux cannot spell — we do."""
    words = " ".join((text or "").split())
    if not words or len(words) > 96:
        return
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as exc:
        log.warning("PIL missing, cannot stamp lettering: {}", exc)
        return
    try:
        im = Image.open(path).convert("RGB")
    except Exception as exc:
        log.warning("stamp open failed: {}", exc)
        return
    width, height = im.size
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    band = max(int(height * 0.30), 120)
    for row in range(band):
        alpha = int(210 * (row / band))
        y = height - band + row
        draw.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))
    size = max(28, int(height * 0.052))
    font = _letter_font(size)
    lines = _wrap_lettering(words, font, int(width * 0.86), draw)
    line_h = size + 10
    block_h = line_h * len(lines)
    y = height - 36 - block_h
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = max(20, (width - tw) // 2)
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2)):
            draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0, 255))
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_h
    out = Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")
    out.save(path, "JPEG", quality=92)
    log.info("stamped lettering on {}", path.name)


def _letter_font(size: int):
    from PIL import ImageFont

    roots = []
    try:
        roots.append(get_settings().files.fonts)
    except Exception:
        pass
    roots.append(Path(__file__).resolve().parents[2] / "resource" / "fonts")
    names = ("Montserrat-Bold.ttf", "Arial.ttf", "arial.ttf")
    for folder in roots:
        for name in names:
            candidate = Path(folder) / name
            if candidate.exists():
                try:
                    return ImageFont.truetype(str(candidate), size)
                except Exception:
                    continue
    return ImageFont.load_default()


def _wrap_lettering(text: str, font, max_width: int, draw) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
        if len(lines) >= 3:
            break
    if current and len(lines) < 4:
        lines.append(current)
    return lines or [text[:40]]


def _is_real_image(head: bytes, size: int) -> bool:
    if size < 8000 or not head:
        return False
    if head.startswith(b"\xff\xd8\xff"):
        return True
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if head.startswith(b"RIFF") and b"WEBP" in head:
        return True
    if head[:1] in {b"<", b"{", b"["}:
        return False
    return False
