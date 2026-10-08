"""Azure Cognitive Services Speech."""

from __future__ import annotations

from pathlib import Path

import httpx

from app.providers.tts.base import BaseTTS, TTSResult
from app.utils.exceptions import ProviderError


class AzureTTS(BaseTTS):
    name = "azure"

    def __init__(self, api_key: str, region: str = "eastus", **kwargs):
        super().__init__(**kwargs)
        if not api_key:
            raise ProviderError("Azure speech key is missing.", stage="tts")
        self.api_key = api_key
        self.region = region

    def synthesize(self, text: str, output: Path, *, voice: str, rate: str = "+0%", volume: str = "+0%", pitch: str = "+0Hz") -> TTSResult:
        ssml = (
            f"<speak version='1.0' xml:lang='en-US'>"
            f"<voice name='{voice}'>"
            f"<prosody rate='{rate}' volume='{volume}' pitch='{pitch}'>"
            f"{_escape(text)}</prosody></voice></speak>"
        )
        url = f"https://{self.region}.tts.speech.microsoft.com/cognitiveservices/v1"
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3",
            "User-Agent": "FrameGenius",
        }
        try:
            response = httpx.post(url, content=ssml.encode("utf-8"), headers=headers, timeout=60)
            response.raise_for_status()
        except Exception as exc:
            raise ProviderError(f"Azure TTS failed: {exc}", stage="tts") from exc
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(response.content)
        duration = max(1.0, len(text.split()) * 0.38)
        return TTSResult(path=output, duration=duration, voice=voice, provider="azure")


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
