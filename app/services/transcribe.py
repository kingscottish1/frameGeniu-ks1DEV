"""Word-level transcription for bleeps + captions.

Tries faster-whisper, then Vosk (small English model, auto-downloaded),
then openai-whisper. No account.
"""

from __future__ import annotations

import json
import wave
import zipfile
from pathlib import Path

import httpx

from app.models.audio import WordTiming
from app.utils.file_manager import ROOT
from app.utils.logger import get_logger

log = get_logger("transcribe")

VOSK_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
VOSK_DIR = ROOT / "models" / "vosk-small-en-us-0.15"


def transcribe_words(audio: Path) -> list[WordTiming]:
    audio = Path(audio)
    if not audio.exists():
        return []
    for fn in (_faster_whisper, _vosk, _openai_whisper):
        try:
            words = fn(audio)
        except Exception as exc:
            log.warning("{} failed: {}", fn.__name__, exc)
            words = []
        if words:
            return words
    log.warning("No local STT — reskin will keep the audio, skip bleeps")
    return []


def stt_ready() -> bool:
    try:
        import faster_whisper  # noqa: F401

        return True
    except Exception:
        pass
    try:
        import vosk  # noqa: F401

        return True
    except Exception:
        pass
    try:
        import whisper  # noqa: F401

        return True
    except Exception:
        return False


def _faster_whisper(audio: Path) -> list[WordTiming]:
    try:
        from faster_whisper import WhisperModel
    except Exception:
        return []
    root = ROOT / "models" / "whisper"
    root.mkdir(parents=True, exist_ok=True)
    try:
        model = WhisperModel("tiny.en", device="cpu", compute_type="int8", download_root=str(root))
        segments, _info = model.transcribe(str(audio), word_timestamps=True, vad_filter=True)
        out: list[WordTiming] = []
        for seg in segments:
            for item in getattr(seg, "words", None) or []:
                token = str(getattr(item, "word", "") or "").strip()
                if not token:
                    continue
                out.append(
                    WordTiming(
                        word=token,
                        start=float(getattr(item, "start", 0.0) or 0.0),
                        end=float(getattr(item, "end", 0.0) or 0.0),
                    )
                )
        log.info("faster-whisper: {} words", len(out))
        return out
    except Exception as exc:
        log.warning("faster-whisper failed: {}", exc)
        return []


def _ensure_vosk_model() -> Path | None:
    marker = VOSK_DIR / "am" / "final.mdl"
    if marker.exists():
        return VOSK_DIR
    VOSK_DIR.parent.mkdir(parents=True, exist_ok=True)
    zpath = VOSK_DIR.parent / "vosk-small-en-us-0.15.zip"
    log.info("Downloading Vosk small English model (~40 MB)…")
    try:
        with httpx.stream("GET", VOSK_URL, timeout=httpx.Timeout(30.0, read=180.0), follow_redirects=True) as resp:
            resp.raise_for_status()
            with zpath.open("wb") as handle:
                for chunk in resp.iter_bytes(1024 * 64):
                    handle.write(chunk)
        with zipfile.ZipFile(zpath) as zf:
            zf.extractall(VOSK_DIR.parent)
        zpath.unlink(missing_ok=True)
    except Exception as exc:
        log.warning("Vosk model download failed: {}", exc)
        return None
    return VOSK_DIR if marker.exists() or VOSK_DIR.exists() else None


def _vosk(audio: Path) -> list[WordTiming]:
    try:
        from vosk import KaldiRecognizer, Model, SetLogLevel
    except Exception:
        return []
    model_dir = _ensure_vosk_model()
    if not model_dir or not model_dir.exists():
        return []
    try:
        SetLogLevel(-1)
        wf = wave.open(str(audio), "rb")
    except Exception as exc:
        log.warning("Vosk could not open wav: {}", exc)
        return []
    try:
        model = Model(str(model_dir))
        rec = KaldiRecognizer(model, wf.getframerate())
        rec.SetWords(True)
        out: list[WordTiming] = []
        while True:
            data = wf.readframes(4000)
            if not data:
                break
            if rec.AcceptWaveform(data):
                out.extend(_vosk_words(rec.Result()))
        out.extend(_vosk_words(rec.FinalResult()))
        log.info("vosk: {} words", len(out))
        return out
    except Exception as exc:
        log.warning("vosk failed: {}", exc)
        return []
    finally:
        try:
            wf.close()
        except Exception:
            pass


def _vosk_words(raw: str) -> list[WordTiming]:
    try:
        payload = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return []
    out: list[WordTiming] = []
    for item in payload.get("result") or []:
        token = str(item.get("word") or "").strip()
        if not token:
            continue
        out.append(
            WordTiming(
                word=token,
                start=float(item.get("start") or 0.0),
                end=float(item.get("end") or 0.0),
            )
        )
    return out


def _openai_whisper(audio: Path) -> list[WordTiming]:
    try:
        import whisper
    except Exception:
        return []
    try:
        model = whisper.load_model("tiny.en")
        result = model.transcribe(str(audio), word_timestamps=True, language="en")
        out: list[WordTiming] = []
        for seg in result.get("segments") or []:
            for item in seg.get("words") or []:
                token = str(item.get("word") or "").strip()
                if not token:
                    continue
                out.append(
                    WordTiming(
                        word=token,
                        start=float(item.get("start") or 0.0),
                        end=float(item.get("end") or 0.0),
                    )
                )
        log.info("whisper: {} words", len(out))
        return out
    except Exception as exc:
        log.warning("openai-whisper failed: {}", exc)
        return []
