"""Pack a finished film into outputs/TODAY — ready to upload, any subject."""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

from app.utils.logger import get_logger
from app.utils.validators import safe_filename

log = get_logger("ship")


def ship_today(
    *,
    output_dir: Path,
    topic: str,
    series_name: str = "",
    series_part: int | None = None,
    video: Path,
    companion: Path | None = None,
    thumb: Path | None = None,
    titles: list[str] | None = None,
    tags: list[str] | None = None,
    captions: Path | None = None,
    post_md: Path | None = None,
) -> dict:
    from app.services.janitor import rotate_today

    output_dir = Path(output_dir)
    rotate_today(output_dir)
    dest = output_dir / "TODAY"
    dest.mkdir(parents=True, exist_ok=True)
    slug = safe_filename(series_name or topic, fallback="film")
    prefix = f"{date.today().isoformat()}_{slug}"
    if series_part:
        prefix += f"_p{int(series_part):02d}"
    copied: dict[str, str] = {}

    def put(src: Path | None, name: str) -> None:
        if not src or not Path(src).exists():
            return
        target = dest / name
        try:
            shutil.copy2(src, target)
            copied[name] = str(target)
        except OSError as exc:
            log.warning("TODAY copy failed {}: {}", name, exc)

    put(Path(video) if video else None, f"{prefix}.mp4")
    if companion and Path(companion).exists():
        put(Path(companion), f"{prefix}_wide.mp4")
    put(Path(thumb) if thumb else None, f"{prefix}_thumb.jpg")
    put(Path(captions) if captions else None, f"{prefix}.srt")
    put(Path(post_md) if post_md else None, f"{prefix}_POST.md")
    if titles:
        (dest / f"{prefix}_titles.txt").write_text("\n".join(titles) + "\n", encoding="utf-8")
        copied["titles"] = str(dest / f"{prefix}_titles.txt")
    if tags:
        (dest / f"{prefix}_tags.txt").write_text(" ".join(tags) + "\n", encoding="utf-8")
        copied["tags"] = str(dest / f"{prefix}_tags.txt")
    log.info("Shipped {} into TODAY ({} files)", prefix, len(copied))
    return {"folder": str(dest), "prefix": prefix, "files": copied}
