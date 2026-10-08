"""Cut a long film into ready-to-post shorts. Never blocks the main MP4."""

from __future__ import annotations

import zipfile
from pathlib import Path

from app.models.script import VideoScript
from app.services import video as video_service
from app.utils.logger import get_logger

log = get_logger("shorts")


def plan_windows(script: VideoScript, duration: float, target: float = 38.0) -> list[tuple[float, float]]:
    """Return (start, end) windows of ~30–50s from scene timings."""
    if duration < 70:
        return []
    scenes = list(script.scenes or [])
    if not scenes:
        step = 40.0
        out = []
        cursor = 0.0
        while cursor + 24 < duration and len(out) < 8:
            end = min(duration, cursor + step)
            if end - cursor >= 24:
                out.append((cursor, end))
            cursor += step - 4
        return out
    windows: list[tuple[float, float]] = []
    start = float(scenes[0].start)
    last = start
    for scene in scenes:
        last = max(float(scene.end or scene.start + scene.duration), last)
        if last - start >= target or scene is scenes[-1]:
            end = min(duration, max(start + 24.0, last))
            if end - start >= 22:
                windows.append((start, end))
            start = float(scene.start)
            if len(windows) >= 8:
                break
    # de-dupe overlaps
    cleaned: list[tuple[float, float]] = []
    prev = -99.0
    for a, b in windows:
        if a - prev < 8:
            continue
        cleaned.append((round(a, 2), round(b, 2)))
        prev = a
    return cleaned[:8]


def cut_shorts(
    *,
    video: Path,
    script: VideoScript,
    duration: float,
    dest_dir: Path,
    task_id: str,
    ffmpeg: str,
) -> dict:
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    windows = plan_windows(script, duration)
    files: list[Path] = []
    for index, (start, end) in enumerate(windows, start=1):
        dest = dest_dir / f"{task_id}_short_{index:02d}.mp4"
        length = max(8.0, end - start)
        cmd = [
            ffmpeg, "-y",
            "-ss", f"{start:.2f}",
            "-t", f"{length:.2f}",
            "-i", str(video),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "aac", "-movflags", "+faststart",
            str(dest),
        ]
        try:
            video_service._run(cmd, f"short-{index}")
            if dest.exists() and dest.stat().st_size > 4000:
                files.append(dest)
        except Exception as exc:
            log.warning("short {} failed: {}", index, exc)
    zip_path = dest_dir / f"{task_id}_shorts.zip"
    if files:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in files:
                zf.write(path, path.name)
    return {
        "count": len(files),
        "files": [str(p) for p in files],
        "zip": str(zip_path) if files and zip_path.exists() else "",
        "windows": windows,
    }
