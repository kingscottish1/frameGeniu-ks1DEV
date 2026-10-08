#!/usr/bin/env python3
"""Ping configured providers. Never prints secret values."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config.settings import get_settings
from app.providers.llm import create_llm
from app.providers.tts import create_tts
from app.providers.media import create_media


def main() -> int:
    settings = get_settings()
    print(f"LLM   provider = {settings.llm_provider}")
    try:
        llm = create_llm()
        print(f"      class    = {llm.__class__.__name__}  ping={llm.ping()}")
    except Exception as exc:
        print(f"      FAIL {exc}")

    print(f"TTS   provider = {settings.tts_provider}")
    try:
        tts = create_tts()
        print(f"      class    = {tts.__class__.__name__}")
    except Exception as exc:
        print(f"      FAIL {exc}")

    print(f"Media provider = {settings.media_provider}")
    try:
        media = create_media()
        print(f"      class    = {None if media is None else media.__class__.__name__}")
    except Exception as exc:
        print(f"      FAIL {exc}")

    try:
        print(f"FFmpeg         = {settings.ffmpeg}")
    except Exception as exc:
        print(f"FFmpeg FAIL    = {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
