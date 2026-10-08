"""Text-to-speech — Edge first, then real OS voices. Never a silent fake bed."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from app.config.settings import get_settings
from app.models.audio import AudioResult, WordTiming
from app.services import tts as tts_service
from app.utils.exceptions import ProviderError
from app.utils.logger import get_logger

log = get_logger("voice")


POSH_VOICE = "en-GB-LibbyNeural"
_US_DEFAULTS = {
    "en-US-JennyNeural", "en-US-AriaNeural", "en-US-GuyNeural", "en-US-AndrewNeural",
    "en-GB-SoniaNeural", "",
}


def _narration_rate(cfg) -> str:
    """Human British read — not the flat AI drone."""
    rate = str(cfg.get("rate") or "-8%").strip()
    if rate in {"", "+0%", "0%", "0", "-15%"}:
        return "-8%"
    return rate


def _pick_voice(cfg, voice: str | None) -> str:
    v = (voice or str(cfg.get("voice") or "")).strip()
    if v in _US_DEFAULTS:
        return POSH_VOICE
    return v or POSH_VOICE


def synthesize(
    text: str,
    output: Path,
    *,
    voice: str | None = None,
    provider: str | None = None,
) -> AudioResult:
    settings = get_settings()
    cfg = settings.tts
    voice_id = _pick_voice(cfg, voice)
    name = provider or settings.tts_provider
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    chunks = _chunk_text(text, 1600)
    if len(chunks) > 1:
        return _synthesize_chunks(chunks, output, voice=voice_id, provider=name)
    last_error: Exception | None = None

    for attempt in range(1, 4):
        try:
            result = tts_service.speak(
                text,
                output,
                provider=name,
                voice=voice_id,
                rate=_narration_rate(cfg),
                volume=str(cfg.get("volume") or "+0%"),
                pitch=str(cfg.get("pitch") or "+0Hz"),
            )
            if Path(result.path).exists() and Path(result.path).stat().st_size >= 64:
                words = [
                    WordTiming(word=item["word"], start=item["start"], end=item["end"])
                    for item in result.words
                    if item.get("word")
                ]
                file_dur = _probe_duration(output)
                duration = file_dur or result.duration or max(1.0, len(text.split()) * 0.42)
                words = _align_words(words, duration)
                return AudioResult(
                    path=str(result.path),
                    duration=duration,
                    words=words,
                    voice=voice_id,
                    provider=result.provider,
                )
            last_error = ProviderError("TTS wrote an empty file.", stage="tts")
        except Exception as exc:
            last_error = exc
            log.warning("TTS attempt {} failed: {}", attempt, exc)
            time.sleep(0.6 * attempt)

    # Real OS voices — not silence.
    try:
        if os.name == "nt":
            _sapi_speak(text, output)
            provider_name = "sapi"
        elif shutil.which("espeak-ng") or shutil.which("espeak"):
            _espeak_speak(text, output)
            provider_name = "espeak"
        else:
            raise ProviderError("No offline voice engine available.", stage="tts")
        duration = _probe_duration(output) or max(1.0, len(text.split()) * 0.42)
        return AudioResult(path=str(output), duration=duration, words=[], voice=voice_id, provider=provider_name)
    except Exception as exc:
        log.error("All TTS engines failed (last={}, os={})", last_error, exc)
        raise ProviderError(
            f"Could not speak the script. Edge TTS failed ({last_error}). OS voice failed ({exc}).",
            stage="tts",
        ) from exc


def _sapi_speak(text: str, output: Path) -> None:
    wav = output.with_suffix(".wav")
    safe = text.replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Speech;"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        f"$s.SetOutputToWaveFile('{str(wav).replace(chr(39), chr(39)+chr(39))}');"
        f"$s.Speak(@'\n{safe}\n'@);"
        "$s.Dispose();"
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0 or not wav.exists() or wav.stat().st_size < 64:
        raise ProviderError(completed.stderr[-400:] or "Windows SAPI failed.", stage="tts")
    _to_mp3(wav, output)


def _espeak_speak(text: str, output: Path) -> None:
    wav = output.with_suffix(".wav")
    binary = shutil.which("espeak-ng") or shutil.which("espeak")
    completed = subprocess.run(
        [binary, "-s", "155", "-w", str(wav), text],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0 or not wav.exists():
        raise ProviderError(completed.stderr[-400:] or "espeak failed.", stage="tts")
    _to_mp3(wav, output)


def _to_mp3(wav: Path, dest: Path) -> None:
    if dest.suffix.lower() == ".wav":
        if wav != dest:
            wav.replace(dest)
        return
    ffmpeg = get_settings().ffmpeg
    completed = subprocess.run(
        [ffmpeg, "-y", "-i", str(wav), "-q:a", "4", str(dest)],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0 or not dest.exists():
        wav.replace(dest.with_suffix(".wav"))
        return
    try:
        wav.unlink()
    except OSError:
        pass


def _chunk_text(text: str, limit: int) -> list[str]:
    text = (text or "").strip()
    if len(text) <= limit:
        return [text] if text else []
    parts: list[str] = []
    buf: list[str] = []
    size = 0
    for sent in re.split(r"(?<=[.!?])\s+", text):
        sent = sent.strip()
        if not sent:
            continue
        if size + len(sent) + 1 > limit and buf:
            parts.append(" ".join(buf))
            buf = [sent]
            size = len(sent)
        else:
            buf.append(sent)
            size += len(sent) + 1
    if buf:
        parts.append(" ".join(buf))
    return parts or [text[:limit]]


def _synthesize_chunks(chunks: list[str], output: Path, *, voice: str, provider: str) -> AudioResult:
    files: list[Path] = []
    words: list[WordTiming] = []
    offset = 0.0
    for index, chunk in enumerate(chunks):
        part = output.parent / f"voice_{index:03d}.mp3"
        result = synthesize(chunk, part, voice=voice, provider=provider)
        for item in result.words:
            words.append(WordTiming(word=item.word, start=item.start + offset, end=item.end + offset))
        offset += result.duration
        files.append(Path(result.path))
        time.sleep(0.35)
    _concat_audio(files, output)
    duration = _probe_duration(output) or offset
    words = _align_words(words, duration)
    return AudioResult(path=str(output), duration=duration, words=words, voice=voice, provider=provider)


def _concat_audio(files: list[Path], dest: Path) -> None:
    ffmpeg = get_settings().ffmpeg
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    listing = dest.parent / "voice_concat.txt"
    lines = []
    for path in files:
        rel = Path(path).name.replace("'", r"'\''")
        lines.append(f"file '{rel}'")
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # PCM join first — copy-concat of Edge MP3s lies about duration and the
    # film then plays silent after the real audio runs out.
    wav = dest.parent / f"{dest.stem}_join.wav"
    completed = subprocess.run(
        [
            ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
            "-ac", "2", "-ar", "44100", str(wav),
        ],
        capture_output=True,
        text=True,
        cwd=str(dest.parent),
    )
    if completed.returncode != 0 or not wav.exists() or wav.stat().st_size < 64:
        raise ProviderError((completed.stderr or "")[-400:] or "Could not join voice chunks.", stage="tts")
    encoded = False
    if dest.suffix.lower() == ".mp3":
        mp3 = subprocess.run(
            [ffmpeg, "-y", "-i", str(wav), "-c:a", "libmp3lame", "-q:a", "4", str(dest)],
            capture_output=True,
            text=True,
        )
        encoded = mp3.returncode == 0 and dest.exists() and dest.stat().st_size > 64
    if not encoded:
        m4a = dest.with_suffix(".m4a")
        aac = subprocess.run(
            [ffmpeg, "-y", "-i", str(wav), "-c:a", "aac", "-b:a", "192k", str(m4a)],
            capture_output=True,
            text=True,
        )
        if aac.returncode == 0 and m4a.exists() and m4a.stat().st_size > 64:
            if dest.suffix.lower() != ".m4a":
                dest.write_bytes(m4a.read_bytes())
            encoded = dest.exists() and dest.stat().st_size > 64
    if not encoded:
        wav.replace(dest.with_suffix(".wav"))
        if dest.suffix.lower() != ".wav":
            dest.write_bytes(Path(str(dest.with_suffix(".wav"))).read_bytes())
    try:
        wav.unlink(missing_ok=True)
    except OSError:
        pass


def join_audio(first: AudioResult, second: AudioResult, dest: Path) -> AudioResult:
    """Glue two voice beds and shift word clocks."""
    dest = Path(dest)
    _concat_audio([Path(first.path), Path(second.path)], dest)
    offset = float(first.duration or 0.0)
    words = list(first.words or [])
    for item in second.words or []:
        words.append(WordTiming(word=item.word, start=item.start + offset, end=item.end + offset))
    duration = _probe_duration(dest) or (offset + float(second.duration or 0.0))
    words = _align_words(words, duration)
    return AudioResult(
        path=str(dest),
        duration=duration,
        words=words,
        voice=first.voice or second.voice,
        provider=first.provider or second.provider,
    )


def _align_words(words: list[WordTiming], duration: float) -> list[WordTiming]:
    if not words or duration <= 1.0:
        return words
    last = max(float(w.end) for w in words)
    if last <= 0.4:
        return words
    scale = duration / last
    if abs(scale - 1.0) < 0.04:
        return words
    log.info("voice clocks {:.1f}s vs file {:.1f}s — stretching x{:.3f}", last, duration, scale)
    return [WordTiming(word=w.word, start=float(w.start) * scale, end=float(w.end) * scale) for w in words]


def _probe_duration(path: Path) -> float:
    try:
        from app.services.video import probe_duration

        return probe_duration(path)
    except Exception:
        return 0.0
