"""Microsoft Edge TTS — free, no API key, word-level timings."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import edge_tts

from app.providers.tts.base import BaseTTS, TTSResult
from app.utils.exceptions import ProviderError

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _run(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


class EdgeTTS(BaseTTS):
    name = "edge"

    async def _speak(self, text: str, output: Path, voice: str, rate: str, volume: str, pitch: str) -> TTSResult:
        spoken = humanize_ssml(text, voice=voice, rate=rate, pitch=pitch)
        communicate = edge_tts.Communicate(text=spoken, voice=voice, rate=rate, volume=volume, pitch=pitch)
        words: list[dict] = []
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("wb") as handle:
            async for chunk in communicate.stream():
                kind = chunk.get("type")
                if kind == "audio":
                    handle.write(chunk["data"])
                elif kind == "WordBoundary":
                    offset = float(chunk.get("offset", 0)) / 10_000_000
                    duration = float(chunk.get("duration", 0)) / 10_000_000
                    words.append(
                        {
                            "word": str(chunk.get("text") or "").strip(),
                            "start": offset,
                            "end": offset + duration,
                        }
                    )
        if not output.exists() or output.stat().st_size < 64:
            raise ProviderError("Edge TTS produced an empty audio file.", stage="tts")
        duration = words[-1]["end"] if words else 0.0
        if duration <= 0:
            duration = max(1.0, len(text.split()) * 0.38)
        return TTSResult(path=output, duration=duration, words=words, voice=voice, provider="edge")

    def synthesize(self, text: str, output: Path, *, voice: str, rate: str = "+0%", volume: str = "+0%", pitch: str = "+0Hz") -> TTSResult:
        if not text.strip():
            raise ProviderError("Cannot speak an empty script.", stage="tts")
        try:
            return _run(self._speak(text, Path(output), voice, rate, volume, pitch))
        except Exception as exc:
            try:
                communicate_text = text
                return _run(self._speak_plain(communicate_text, Path(output), voice, rate, volume, pitch))
            except Exception:
                raise ProviderError(f"Edge TTS failed: {exc}", stage="tts") from exc

    async def _speak_plain(self, text: str, output: Path, voice: str, rate: str, volume: str, pitch: str) -> TTSResult:
        communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, volume=volume, pitch=pitch)
        words: list[dict] = []
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("wb") as handle:
            async for chunk in communicate.stream():
                kind = chunk.get("type")
                if kind == "audio":
                    handle.write(chunk["data"])
                elif kind == "WordBoundary":
                    offset = float(chunk.get("offset", 0)) / 10_000_000
                    duration = float(chunk.get("duration", 0)) / 10_000_000
                    words.append(
                        {
                            "word": str(chunk.get("text") or "").strip(),
                            "start": offset,
                            "end": offset + duration,
                        }
                    )
        if not output.exists() or output.stat().st_size < 64:
            raise ProviderError("Edge TTS produced an empty audio file.", stage="tts")
        duration = words[-1]["end"] if words else max(1.0, len(text.split()) * 0.38)
        return TTSResult(path=output, duration=duration, words=words, voice=voice, provider="edge")

    def list_voices(self) -> list[dict]:
        try:
            voices = _run(edge_tts.list_voices())
        except Exception:
            return []
        out = []
        for item in voices:
            out.append(
                {
                    "id": item.get("ShortName"),
                    "name": item.get("FriendlyName") or item.get("ShortName"),
                    "locale": item.get("Locale"),
                    "gender": str(item.get("Gender") or "").lower(),
                    "provider": "edge",
                }
            )
        return out


def _xml(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _parse_rate(rate: str) -> int:
    raw = (rate or "-8%").strip()
    match = re.search(r"(-?\d+)", raw)
    try:
        return int(match.group(1)) if match else -8
    except ValueError:
        return -8


def humanize_ssml(text: str, *, voice: str = "en-GB-SoniaNeural", rate: str = "-8%", pitch: str = "+0Hz") -> str:
    """British documentary pacing — pauses and tiny rate/pitch drift so it doesn't drone."""
    blob = " ".join((text or "").split())
    if not blob:
        return blob
    if blob.lstrip().lower().startswith("<speak"):
        return blob
    sentences = [s.strip() for s in _SENT_SPLIT.split(blob) if s.strip()]
    if not sentences:
        sentences = [blob]
    base = _parse_rate(rate)
    parts: list[str] = []
    for index, sent in enumerate(sentences):
        drift = (-3, -1, 0, 1, -2, 2, -1, 0)[index % 8]
        r = max(-18, min(4, base + drift))
        p = (-1, 0, 1, 0, -1, 1, 0, -2)[index % 8]
        pause = 420 if index % 5 == 4 else (260 if sent.endswith("?") else 220)
        sign = "+" if r >= 0 else ""
        ps = "+" if p >= 0 else ""
        parts.append(
            f'<prosody rate="{sign}{r}%" pitch="{ps}{p}Hz">{_xml(sent)}</prosody>'
            f'<break time="{pause}ms"/>'
        )
    lang = "en-GB" if "en-GB" in (voice or "") else "en-US"
    return (
        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{lang}">'
        + "".join(parts)
        + "</speak>"
    )
