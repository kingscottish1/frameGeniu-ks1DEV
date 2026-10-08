#!/usr/bin/env python3
"""Render a real short locally and print the MP4 path."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.models.video import VideoParams
from app.services import script as script_service
from app.services import stock_media
from app.services import subtitle as subtitle_service
from app.services import video as video_service
from app.utils.file_manager import get_ffmpeg


def _tone(path: Path, seconds: float = 10.0) -> None:
    import subprocess

    ffmpeg = get_ffmpeg()
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi",
        "-i", f"sine=frequency=220:sample_rate=44100:duration={seconds}",
        "-q:a", "6",
        str(path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def main() -> int:
    work = ROOT / "outputs" / "tasks" / "smoke13"
    work.mkdir(parents=True, exist_ok=True)
    params = VideoParams(
        topic="The night the vault cameras went dark",
        template="crime",
        duration=12,
        llm_provider="studio",
        subtitle_enabled=True,
        bgm_enabled=True,
    )
    script = script_service.generate_script(
        params.topic,
        template=params.template,
        duration=params.duration,
        provider="studio",
    )
    print("script scenes", len(script.scenes), "title", script.title)
    audio = work / "voice.mp3"
    try:
        from app.services import voice as voice_service

        spoken = voice_service.synthesize(script.narration[:400], audio, provider="edge")
        print("voice", spoken.provider, spoken.duration)
        audio_path = Path(spoken.path)
        duration = spoken.duration
        words = spoken.words
    except Exception as exc:
        print("edge tts skipped:", exc)
        _tone(audio, 10)
        audio_path = audio
        duration = 10.0
        words = []
    clips = stock_media.collect_clips(script, params, work)
    print("clips", len(clips), [c.path.name for c in clips[:6]])
    track = subtitle_service.build_subtitles(
        script, words=words, audio_path=audio_path, duration=duration, workdir=work
    )
    print("cues", len(track.cues), "ass", track.ass_path)
    dest = ROOT / "outputs" / "videos" / "smoke13_crime.mp4"
    video_service.compose_video(
        clips=clips,
        audio_path=audio_path,
        script=script,
        params=params,
        subtitles=track,
        workdir=work,
        output=dest,
        on_progress=lambda p, m: print(f"  {p}% {m}"),
    )
    size = dest.stat().st_size
    print("OUTPUT", dest, size)
    if size < 1024:
        print("FAIL empty")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
