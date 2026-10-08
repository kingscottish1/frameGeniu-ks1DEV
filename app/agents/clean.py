"""Clean agent — pull audio off an uploaded film, bleep swears, keep the rest of the sound."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.models.audio import AudioResult
from app.models.script import Scene, VideoScript
from app.services.bleep import bleep_audio, profane_ranges
from app.services.transcribe import transcribe_words
from app.services.video import probe_duration

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


class AudioCleanAgent(BaseAgent):
    name = "clean"
    label = "Clean"
    start_progress = 2
    end_progress = 24

    def run(self, ctx: AgentContext) -> AgentResult:
        src = Path(str(getattr(ctx.params, "source_video", "") or ""))
        if not src.exists():
            return self.fail("No uploaded video.")
        local = ctx.workdir / f"source{src.suffix.lower() or '.mp4'}"
        try:
            if src.resolve() != local.resolve():
                shutil.copy2(src, local)
                src = local
        except Exception:
            pass
        ctx.progress(self.start_progress, self.name, "Pulling the audio")
        from app.config.settings import get_settings

        ffmpeg = get_settings().ffmpeg
        video_dur = probe_duration(src) or float(ctx.params.duration or 30)
        bed = _extract_bed(ffmpeg, src, ctx.workdir)
        if bed is None or not _has_signal(ffmpeg, bed):
            return self.fail("Could not pull audio off that video.")
        listen = _extract_listen(ffmpeg, src, ctx.workdir) or bed
        duration = probe_duration(bed) or video_dur
        ctx.progress(10, self.name, "Listening for swears")
        words = transcribe_words(listen)
        hits = profane_ranges(words) if getattr(ctx.params, "bleep_profanity", True) else []
        voice = ctx.workdir / "voice.m4a"
        if hits:
            ctx.progress(16, self.name, f"Bleeping {len(hits)} words — keeping the rest of the sound")
            bleep_audio(bed, voice, hits, duration)
        else:
            shutil.copy2(bed, voice)
        if not voice.exists() or not _has_signal(ffmpeg, voice):
            self.log.warning("bleep output silent — using original audio")
            shutil.copy2(bed, voice)
        duration = probe_duration(voice) or duration or video_dur
        if duration < video_dur * 0.7:
            duration = video_dur
        try:
            ctx.params.duration = float(duration)
        except Exception:
            pass
        audio = AudioResult(
            path=str(voice),
            duration=duration,
            words=words,
            voice="source",
            provider="upload",
        )
        script = _script_from_speech(ctx.params.topic, words, duration)
        script_path = ctx.workdir / "script.json"
        script_path.write_text(script.model_dump_json(indent=2), encoding="utf-8")
        ctx.payload["audio"] = audio
        ctx.payload["script"] = script
        ctx.payload["script_path"] = script_path
        ctx.payload["bleeps"] = len(hits)
        ctx.progress(self.end_progress, self.name, f"{duration:.0f}s audio · {len(hits)} bleeps · {len(words)} words")
        return AgentResult(
            stage=self.name,
            message=f"{len(hits)} bleeps",
            data={"duration": duration, "bleeps": len(hits), "words": len(words)},
        )


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    kwargs: dict = {"capture_output": True, "text": True}
    if _CREATE_NO_WINDOW:
        kwargs["creationflags"] = _CREATE_NO_WINDOW
    return subprocess.run(cmd, **kwargs)


def _ok(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 1000


def _extract_bed(ffmpeg: str, src: Path, workdir: Path) -> Path | None:
    """Keep the original soundtrack. Never downsample this — that's the film's voice."""
    attempts = [
        (workdir / "source.m4a", ["-map", "0:a:0", "-vn", "-ac", "2", "-ar", "44100", "-c:a", "aac", "-b:a", "192k"]),
        (workdir / "source.mp3", ["-map", "0:a:0", "-vn", "-ac", "2", "-ar", "44100", "-c:a", "libmp3lame", "-q:a", "4"]),
        (workdir / "source.wav", ["-map", "0:a:0", "-vn", "-ac", "2", "-ar", "44100"]),
        (workdir / "source2.m4a", ["-vn", "-ac", "2", "-ar", "44100", "-c:a", "aac", "-b:a", "192k"]),
    ]
    for dest, extra in attempts:
        dest.parent.mkdir(parents=True, exist_ok=True)
        cmd = [ffmpeg, "-y", "-i", str(src), *extra, str(dest)]
        completed = _run(cmd)
        if completed.returncode == 0 and _ok(dest):
            return dest
        dest.unlink(missing_ok=True)
    return None


def _extract_listen(ffmpeg: str, src: Path, workdir: Path) -> Path | None:
    dest = workdir / "listen.wav"
    cmd = [ffmpeg, "-y", "-i", str(src), "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "16000", str(dest)]
    completed = _run(cmd)
    if completed.returncode == 0 and _ok(dest):
        return dest
    cmd = [ffmpeg, "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", str(dest)]
    completed = _run(cmd)
    return dest if completed.returncode == 0 and _ok(dest) else None


def _has_signal(ffmpeg: str, path: Path) -> bool:
    if not _ok(path):
        return False
    cmd = [ffmpeg, "-i", str(path), "-af", "volumedetect", "-f", "null", "-"]
    completed = _run(cmd)
    blob = (completed.stderr or "") + (completed.stdout or "")
    mean = _db(blob, "mean_volume")
    peak = _db(blob, "max_volume")
    if mean is None and peak is None:
        return probe_duration(path) > 0.4
    if peak is not None and peak > -35:
        return True
    if mean is not None and mean > -50:
        return True
    return False


def _db(blob: str, key: str) -> float | None:
    marker = f"{key}:"
    for line in blob.splitlines():
        if marker in line:
            try:
                return float(line.split(marker, 1)[1].strip().split()[0])
            except (TypeError, ValueError, IndexError):
                return None
    return None


def _script_from_speech(topic: str, words, duration: float) -> VideoScript:
    topic = (topic or "uploaded film").strip() or "uploaded film"
    scenes: list[Scene] = []
    if words:
        bucket: list[str] = []
        start = float(words[0].start)
        last = start
        for item in words:
            if not bucket:
                start = float(item.start)
            token = str(item.word or "").strip()
            if token:
                bucket.append(token)
            last = float(item.end)
            long_enough = last - start >= 3.6 or len(bucket) >= 12
            if long_enough and bucket:
                narr = " ".join(bucket)
                scenes.append(
                    Scene(
                        narration=narr,
                        search=topic,
                        visual=narr[:80],
                        duration=max(2.6, last - start),
                    )
                )
                bucket = []
        if bucket:
            narr = " ".join(bucket)
            scenes.append(
                Scene(
                    narration=narr,
                    search=topic,
                    visual=narr[:80],
                    duration=max(2.6, last - start),
                )
            )
    if not scenes:
        scenes = [
            Scene(narration=topic, search=topic, visual=topic, duration=max(8.0, float(duration or 8))),
        ]
    script = VideoScript(
        title=topic.title()[:80],
        description=f"Reskin of uploaded audio about {topic}.",
        hook=scenes[0].narration[:140],
        template="story",
        scenes=scenes,
        raw_text=" ".join(s.narration for s in scenes),
    )
    script.apply_timings()
    return script
