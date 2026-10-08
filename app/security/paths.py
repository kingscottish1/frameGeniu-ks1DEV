"""Path traversal guards for downloads and uploads."""

from __future__ import annotations

from pathlib import Path

from app.utils.exceptions import ValidationError
from app.utils.file_manager import ROOT


def safe_under(path: str | Path, *roots: Path) -> Path:
    candidate = Path(path).expanduser()
    try:
        resolved = candidate.resolve()
    except OSError as exc:
        raise ValidationError("Invalid path.", stage="path") from exc
    allowed = []
    for root in roots or (ROOT / "outputs",):
        try:
            allowed.append(root.resolve())
        except OSError:
            continue
    for root in allowed:
        try:
            resolved.relative_to(root)
            if not resolved.exists():
                raise ValidationError("File does not exist.", stage="path")
            return resolved
        except ValueError:
            continue
    raise ValidationError("Path is outside the allowed directories.", stage="path")


def is_safe_task_id(task_id: str) -> bool:
    return bool(task_id) and task_id.replace("_", "").replace("-", "").isalnum() and len(task_id) <= 64
