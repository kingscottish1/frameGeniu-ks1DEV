"""Paths, FFmpeg resolution, and task workspace helpers."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def get_ffmpeg(explicit: str | None = None) -> str:
    """Return a usable ffmpeg binary path."""
    if explicit:
        candidate = Path(explicit)
        if candidate.exists():
            return str(candidate)
    env_path = os.environ.get("FFMPEG_BINARY") or os.environ.get("FFMPEG_PATH")
    if env_path and Path(env_path).exists():
        return env_path
    which = shutil.which("ffmpeg")
    if which:
        return which
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pragma: no cover
        raise FileNotFoundError(
            "FFmpeg was not found. Install ffmpeg or keep imageio-ffmpeg installed."
        ) from exc


def get_ffprobe(ffmpeg_bin: str | None = None) -> str | None:
    ffmpeg_bin = ffmpeg_bin or get_ffmpeg()
    sibling = Path(ffmpeg_bin).with_name("ffprobe")
    if sibling.exists():
        return str(sibling)
    which = shutil.which("ffprobe")
    return which


class FileManager:
    """Project-wide path resolver. Created once by settings."""

    def __init__(self, root: Path | None = None, output_dir: str = "outputs", resource_dir: str = "resource"):
        self.root = Path(root) if root else ROOT
        self.output_dir = self._resolve(output_dir)
        self.resource_dir = self._resolve(resource_dir)
        self.videos = self.output_dir / "videos"
        self.scripts = self.output_dir / "scripts"
        self.logs = self.output_dir / "logs"
        self.thumbnails = self.output_dir / "thumbnails"
        self.tasks = self.output_dir / "tasks"
        self.songs = self.resource_dir / "songs"
        self.fonts = self.resource_dir / "fonts"
        self.templates = self.resource_dir / "templates"
        self.icons = self.resource_dir / "icons"
        self.media = self.resource_dir / "media"
        self.images = self.output_dir / "images"
        self.today = self.output_dir / "TODAY"
        self.posts = self.output_dir / "posts"
        self.ensure_runtime()

    def _resolve(self, path: str | Path) -> Path:
        p = Path(path)
        if not p.is_absolute():
            p = self.root / p
        return p

    def ensure_runtime(self) -> None:
        for folder in (
            self.videos,
            self.scripts,
            self.logs,
            self.thumbnails,
            self.tasks,
            self.songs,
            self.fonts,
            self.templates,
            self.icons,
            self.media,
            self.images,
            self.today,
            self.posts,
        ):
            folder.mkdir(parents=True, exist_ok=True)

    def task_dir(self, task_id: str) -> Path:
        path = self.tasks / task_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def font_path(self, name: str) -> Path:
        candidate = self.fonts / name
        if candidate.exists():
            return candidate
        matches = list(self.fonts.glob("*.ttf")) + list(self.fonts.glob("*.otf"))
        if matches:
            return matches[0]
        return candidate

    def list_songs(self) -> list[Path]:
        songs: list[Path] = []
        for ext in ("*.mp3", "*.wav", "*.m4a", "*.aac", "*.ogg"):
            songs.extend(sorted(self.songs.glob(ext)))
        return songs

    def list_local_media(self) -> list[Path]:
        files: list[Path] = []
        for folder in (self.media, self.templates / "covers"):
            if not folder.exists():
                continue
            for ext in ("*.mp4", "*.mov", "*.webm", "*.jpg", "*.jpeg", "*.png", "*.webp"):
                files.extend(sorted(folder.glob(ext)))
        return files
