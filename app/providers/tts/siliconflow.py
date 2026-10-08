"""SiliconFlow CosyVoice TTS."""

from __future__ import annotations

from pathlib import Path

import httpx

from app.providers.tts.base import BaseTTS, TTSResult
from app.utils.exceptions import ProviderError


class SiliconFlowTTS(BaseTTS):
    name = "siliconflow"

    def __init__(self, api_key: str, base_url: str = "https://api.siliconflow.cn/v1", **kwargs):
        super().__init__(**kwargs)
        if not api_key:
            raise ProviderError("SiliconFlow API key is missing.", stage="tts")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def synthesize(self, text: str, output: Path, *, voice: str, rate: str = "+0%", volume: str = "+0%", pitch: str = "+0Hz") -> TTSResult:
        url = f"{self.base_url}/audio/speech"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {"model": "FunAudioLLM/CosyVoice2-0.5B", "voice": voice, "input": text, "response_format": "mp3"}
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=90)
            response.raise_for_status()
        except Exception as exc:
            raise ProviderError(f"SiliconFlow TTS failed: {exc}", stage="tts") from exc
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(response.content)
        return TTSResult(path=output, duration=max(1.0, len(text.split()) * 0.38), voice=voice, provider="siliconflow")
