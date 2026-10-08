"""Pytest fixtures for FrameGenius."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("FRAMEGENIUS_AUTH", "0")
os.environ.setdefault("FRAMEGENIUS_MASTER_KEY", "dGVzdC1mcmFtZWdlbml1cy1tYXN0ZXIta2V5LTMyIQ")
os.environ.setdefault("FRAMEGENIUS_ADMIN_USER", "admin")
os.environ.setdefault("FRAMEGENIUS_ADMIN_PASSWORD", "test-password-for-ci")
os.environ.setdefault("FRAMEGENIUS_EXPOSE_DOCS", "0")
os.environ.setdefault("FRAMEGENIUS_DATA_DIR", str(ROOT / ".test-data"))

import pytest

from app.models.script import Scene, VideoScript
from app.models.video import AspectRatio, VideoParams


@pytest.fixture
def params() -> VideoParams:
    return VideoParams(topic="deep work", template="motivational", aspect_ratio=AspectRatio.PORTRAIT, duration=20)


@pytest.fixture
def script() -> VideoScript:
    scenes = [
        Scene(narration="Start now.", search="sunrise mountain", duration=3),
        Scene(narration="Stay longer than your mood.", search="ocean dawn", duration=3),
    ]
    item = VideoScript(title="Deep Work", scenes=scenes, raw_text="Start now. Stay longer than your mood.")
    item.apply_timings()
    return item
