"""Intro / end cards and big-text thumbnails. PIL only — no FFmpeg text filters."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.utils.file_manager import ROOT


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        ROOT / "resource" / "fonts" / "Montserrat-Bold.ttf",
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                continue
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, limit: int = 5) -> list[str]:
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
    return lines[:limit]


def paint_card(
    dest: Path,
    *,
    kicker: str,
    headline: str,
    footer: str = "",
    size: tuple[int, int] = (1080, 1920),
    ink: tuple[int, int, int] = (243, 210, 122),
    bg: tuple[int, int, int] = (8, 10, 16),
) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    width, height = size
    img = Image.new("RGB", (width, height), bg)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle([0, int(height * 0.32), width, int(height * 0.72)], fill=(20, 16, 8, 90))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    img = img.filter(ImageFilter.GaussianBlur(radius=0.4))
    draw = ImageDraw.Draw(img)
    margin = int(width * 0.08)
    kicker_font = _font(max(22, width // 26))
    title_font = _font(max(40, width // 11))
    foot_font = _font(max(20, width // 28))
    if kicker:
        draw.text((margin, int(height * 0.28)), kicker.upper()[:42], font=kicker_font, fill=(62, 224, 255))
    lines = _wrap(draw, headline, title_font, width - margin * 2) or [headline[:24]]
    y = int(height * 0.36)
    for line in lines:
        draw.text((margin, y), line, font=title_font, fill=ink)
        y += int(getattr(title_font, "size", 48) * 1.12)
    bar_y = int(height * 0.78)
    draw.rectangle([margin, bar_y, margin + int(width * 0.22), bar_y + 6], fill=ink)
    if footer:
        draw.text((margin, bar_y + 22), footer[:48], font=foot_font, fill=(200, 200, 200))
    img.save(dest, "JPEG", quality=90)
    return dest


def paint_thumbnail(
    dest: Path,
    *,
    headline: str,
    kicker: str = "",
    footer: str = "",
    base: Path | None = None,
    size: tuple[int, int] = (1080, 1920),
) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    width, height = size
    if base and Path(base).exists():
        try:
            img = Image.open(base).convert("RGB")
            img = img.resize((width, height), Image.Resampling.LANCZOS)
        except Exception:
            img = Image.new("RGB", (width, height), (10, 12, 18))
    else:
        img = Image.new("RGB", (width, height), (10, 12, 18))
    shade = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    sd.rectangle([0, int(height * 0.42), width, height], fill=(0, 0, 0, 160))
    img = Image.alpha_composite(img.convert("RGBA"), shade).convert("RGB")
    draw = ImageDraw.Draw(img)
    margin = int(width * 0.07)
    if kicker:
        draw.text((margin, int(height * 0.48)), kicker.upper()[:36], font=_font(max(22, width // 24)), fill=(62, 224, 255))
    title_font = _font(max(44, width // 10))
    lines = _wrap(draw, headline, title_font, width - margin * 2, 4) or [headline[:20]]
    y = int(height * 0.55)
    for line in lines:
        draw.text((margin + 2, y + 2), line, font=title_font, fill=(0, 0, 0))
        draw.text((margin, y), line, font=title_font, fill=(245, 232, 170))
        y += int(getattr(title_font, "size", 52) * 1.1)
    if footer:
        draw.text((margin, height - int(height * 0.1)), footer[:40], font=_font(max(20, width // 28)), fill=(210, 210, 210))
    img.save(dest, "JPEG", quality=91)
    return dest


def hook_words(text: str, limit: int = 7) -> str:
    words = [w for w in (text or "").split() if w]
    if not words:
        return "WATCH THIS"
    return " ".join(words[:limit]).upper()
