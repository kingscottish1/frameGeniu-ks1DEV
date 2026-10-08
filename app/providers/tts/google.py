"""Google Cloud Text-to-Speech (REST)."""

from __future__ import annotations

import base64
from pathlib import Path

import httpx

from app.providers.tts.base import BaseTTS, TTSResult
from app.utils.exceptions import ProviderError


class GoogleTTS(BaseTTS):
    name = "google"

    def __init__(self, api_key: str, **kwargs):
        super().__init__(**kwargs)
        if not api_key:
            raise ProviderError("Google TTS API key is missing.", stage="tts")
        self.api_key = api_key

    def synthesize(self, text: str, output: Path, *, voice: str, rate: str = "+0%", volume: str = "+0%", pitch: str = "+0Hz") -> TTSResult:
        speaking_rate = 1.0
        try:
            speaking_rate = 1.0 + float(rate.replace("%", "")) / 100.0
        except ValueError:
            pass
        locale = "en-US"
        if len(voice) >= 5 and voice[2] == "-":
            locale = voice[:5]
        payload = {
            "input": {"text": text},
            "voice": {"languageCode": locale, "name": voice},
            "audioConfig": {"audioEncoding": "MP3", "speakingRate": max(0.25, min(4.0, speaking_rate))},
        }
        url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={self.api_key}"
        try:
            response = httpx.post(url, json=payload, timeout=60)
            response.raise_for_status()
            audio_b64 = response.json().get("audioContent")
            if not audio_b64:
                raise ProviderError("Google TTS returned no audio.", stage="tts")
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"Google TTS failed: {exc}", stage="tts") from exc
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(base64.b64decode(audio_b64))
        return TTSResult(path=output, duration=max(1.0, len(text.split()) * 0.38), voice=voice, provider="google")
