"""Per-scene cinematic stills so every render has unique B-roll."""

from __future__ import annotations

import hashlib
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.utils.file_manager import ROOT
from app.utils.logger import get_logger

log = get_logger("stills")

PALETTES = {
    "crime": [(12, 10, 14), (48, 18, 18), (212, 175, 55), (180, 40, 50)],
    "news": [(8, 14, 28), (20, 40, 80), (62, 224, 255), (230, 230, 240)],
    "motivational": [(10, 12, 18), (40, 28, 12), (240, 210, 122), (230, 180, 80)],
    "educational": [(10, 16, 22), (18, 40, 48), (120, 200, 190), (240, 240, 240)],
    "entertainment": [(18, 8, 24), (80, 20, 70), (255, 80, 140), (250, 220, 80)],
    "product": [(8, 10, 16), (24, 28, 40), (62, 224, 255), (212, 175, 55)],
    "story": [(14, 12, 18), (50, 30, 40), (220, 160, 130), (240, 220, 200)],
}


def _palette(template: str, seed: str) -> list[tuple[int, int, int]]:
    base = PALETTES.get((template or "").lower(), PALETTES["motivational"])
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    shift = digest[0] % 24
    return [((r + shift) % 256, (g + shift // 2) % 256, (b + shift // 3) % 256) for r, g, b in base]


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        ROOT / "resource" / "fonts" / "Montserrat-Bold.ttf",
        ROOT / "resource" / "fonts" / "Arial.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                continue
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = [w for w in (text or "").split() if w]
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines[:5]


def render_still(
    *,
    dest: Path,
    query: str,
    topic: str,
    template: str = "motivational",
    size: tuple[int, int] = (1080, 1920),
    index: int = 0,
) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    width, height = size
    seed = f"{topic}|{query}|{index}"
    rng = random.Random(hashlib.sha256(seed.encode()).hexdigest())
    bg, mid, accent, ink = _palette(template, seed)

    band = Image.new("RGB", (1, height), bg)
    pix = band.load()
    for y in range(height):
        t = y / max(1, height - 1)
        wave = 0.5 + 0.5 * math.sin(t * math.pi * 2 + index)
        pix[0, y] = (
            max(0, min(255, int(bg[0] * (1 - t) + mid[0] * t + accent[0] * 0.08 * wave))),
            max(0, min(255, int(bg[1] * (1 - t) + mid[1] * t + accent[1] * 0.08 * wave))),
            max(0, min(255, int(bg[2] * (1 - t) + mid[2] * t + accent[2] * 0.08 * wave))),
        )
    img = band.resize((width, height), Image.BILINEAR)
    try:
        noise = Image.effect_noise((width, height), 18).convert("L")
        img = Image.blend(img, Image.merge("RGB", (noise, noise, noise)), 0.07)
    except Exception:
        pass

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw_o = ImageDraw.Draw(overlay)
    for _ in range(4):
        x0 = rng.randint(-width // 4, width)
        y0 = rng.randint(-height // 8, height)
        x1 = x0 + rng.randint(width // 3, width)
        y1 = y0 + rng.randint(80, 280)
        color = (*accent, rng.randint(18, 40))
        draw_o.rectangle([x0, y0, x1, y1], fill=color)
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    img = img.filter(ImageFilter.GaussianBlur(radius=0.6))

    # Atmosphere only — never stamp the prompt as text. Crown paints real pictures.
    draw = ImageDraw.Draw(img)
    margin = int(width * 0.08)
    bar_y = height - int(height * 0.14)
    draw.rectangle([margin, bar_y, margin + int(width * 0.22), bar_y + 5], fill=accent)
    img.save(dest, "JPEG", quality=90)
    return dest


def render_scene_stills(
    *,
    queries: list[str],
    topic: str,
    template: str,
    dest_dir: Path,
    size: tuple[int, int],
) -> list[Path]:
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    terms = queries or [topic]
    if len(terms) < 4:
        extras = [topic, f"{topic} night", f"{topic} close up", f"{topic} city"]
        terms = (terms + extras)[:6]
    for index, query in enumerate(terms):
        dest = dest_dir / f"still_{index:02d}.jpg"
        try:
            render_still(dest=dest, query=query, topic=topic, template=template, size=size, index=index)
            paths.append(dest)
        except Exception as exc:
            log.warning("still {} failed: {}", query, exc)
    return paths
