"""Self-hosted Chatterbox TTS."""

from __future__ import annotations

from pathlib import Path

import httpx

from app.providers.tts.base import BaseTTS, TTSResult
from app.utils.exceptions import ProviderError


class ChatterboxTTS(BaseTTS):
    name = "chatterbox"

    def __init__(self, base_url: str = "http://127.0.0.1:8001", **kwargs):
        super().__init__(**kwargs)
        self.base_url = base_url.rstrip("/")

    def synthesize(self, text: str, output: Path, *, voice: str, rate: str = "+0%", volume: str = "+0%", pitch: str = "+0Hz") -> TTSResult:
        url = f"{self.base_url}/v1/audio/speech"
        payload = {"input": text, "voice": voice or "default", "response_format": "mp3"}
        try:
            response = httpx.post(url, json=payload, timeout=120)
            response.raise_for_status()
        except Exception as exc:
            raise ProviderError(f"Chatterbox TTS failed: {exc}", stage="tts") from exc
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(response.content)
        return TTSResult(path=output, duration=max(1.0, len(text.split()) * 0.38), voice=voice, provider="chatterbox")
