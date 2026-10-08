"""TTS provider abstraction."""

from __future__ import annotations

from pathlib import Path

from app.providers.tts import BaseTTS, TTSResult, create_tts


def get_tts(provider: str | None = None) -> BaseTTS:
    return create_tts(provider)


def speak(text: str, output: Path, *, provider: str | None = None, voice: str, rate: str = "+0%", volume: str = "+0%", pitch: str = "+0Hz") -> TTSResult:
    return get_tts(provider).synthesize(text, output, voice=voice, rate=rate, volume=volume, pitch=pitch)
