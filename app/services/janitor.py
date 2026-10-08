"""Wipe old render scratch so the disk does not die mid-queue."""

from __future__ import annotations

import shutil
import time
from datetime import date
from pathlib import Path

from app.config.settings import get_settings
from app.utils.logger import get_logger

log = get_logger("janitor")


def sweep(*, task_hours: float = 36.0, image_hours: float = 168.0) -> dict:
    settings = get_settings()
    files = settings.files
    now = time.time()
    removed = 0
    freed = 0

    def wipe(path: Path) -> None:
        nonlocal removed, freed
        try:
            size = _size(path)
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
            removed += 1
            freed += size
        except OSError as exc:
            log.debug("janitor skip {}: {}", path, exc)

    cutoff_tasks = now - task_hours * 3600
    if files.tasks.exists():
        for folder in files.tasks.iterdir():
            if not folder.is_dir():
                continue
            try:
                age = folder.stat().st_mtime
            except OSError:
                continue
            if age < cutoff_tasks:
                wipe(folder)

    cutoff_img = now - image_hours * 3600
    if files.images.exists():
        for item in files.images.iterdir():
            try:
                if item.is_file() and item.stat().st_mtime < cutoff_img:
                    wipe(item)
            except OSError:
                continue

    rotate_today(files.output_dir)
    if removed:
        log.info("Janitor removed {} old folders/files (~{} MB)", removed, freed // (1024 * 1024))
    return {"removed": removed, "freed_mb": freed // (1024 * 1024)}


def rotate_today(output_dir: Path) -> None:
    today = output_dir / "TODAY"
    stamp = today / ".day"
    day = date.today().isoformat()
    if not today.exists():
        today.mkdir(parents=True, exist_ok=True)
        stamp.write_text(day, encoding="utf-8")
        return
    prev = stamp.read_text(encoding="utf-8").strip() if stamp.exists() else ""
    if prev == day:
        return
    if prev:
        archive = output_dir / "posts" / prev
        archive.mkdir(parents=True, exist_ok=True)
        for item in today.iterdir():
            if item.name == ".day":
                continue
            dest = archive / item.name
            try:
                if dest.exists():
                    continue
                shutil.move(str(item), str(dest))
            except OSError:
                pass
    stamp.write_text(day, encoding="utf-8")


def _size(path: Path) -> int:
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                pass
    return total
