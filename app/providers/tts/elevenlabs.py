"""ElevenLabs TTS."""

from __future__ import annotations

from pathlib import Path

import httpx

from app.providers.tts.base import BaseTTS, TTSResult
from app.utils.exceptions import ProviderError


class ElevenLabsTTS(BaseTTS):
    name = "elevenlabs"

    def __init__(self, api_key: str, model: str = "eleven_multilingual_v2", **kwargs):
        super().__init__(**kwargs)
        if not api_key:
            raise ProviderError("ElevenLabs API key is missing.", stage="tts")
        self.api_key = api_key
        self.model = model

    def synthesize(self, text: str, output: Path, *, voice: str, rate: str = "+0%", volume: str = "+0%", pitch: str = "+0Hz") -> TTSResult:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
        headers = {"xi-api-key": self.api_key, "accept": "audio/mpeg", "content-type": "application/json"}
        payload = {
            "text": text,
            "model_id": self.model,
            "voice_settings": {"stability": 0.45, "similarity_boost": 0.75},
        }
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=90)
            response.raise_for_status()
        except Exception as exc:
            raise ProviderError(f"ElevenLabs TTS failed: {exc}", stage="tts") from exc
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(response.content)
        return TTSResult(path=output, duration=max(1.0, len(text.split()) * 0.38), voice=voice, provider="elevenlabs")
