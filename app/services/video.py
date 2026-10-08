"""Video composition and rendering via FFmpeg.

Windows note: FFmpeg filtergraphs treat ':' as an option separator, so a
path like C:\\Users\\... blows up the `ass=` / `subtitles=` / `fontsdir=`
filters (the 74% editor crash). Every filter path in this module is a
simple relative name, and FFmpeg is launched with cwd set to the task
folder. Caption burn is best-effort — the MP4 is always exported.
"""

from __future__ import annotations

import os
import random
import re
import shlex
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from app.config.settings import get_settings
from app.models.script import VideoScript
from app.models.subtitle import SubtitleTrack
from app.models.video import VideoParams
from app.providers.media.base import MediaClip
from app.utils.exceptions import RenderError
from app.utils.file_manager import ROOT
from app.utils.logger import get_logger

log = get_logger("video")

_DURATION_RE = re.compile(r"Duration: (\d+):(\d+):(\d+(?:.\d+)?)")
_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+(?:.\d+)?)")
ProgressCb = Callable[[int, str], None]

_CREATE_NO_WINDOW = 0
if os.name == "nt":
    _CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def probe_duration(path: str | Path) -> float:
    """Header duration can lie on concatenated Edge MP3s (the 3:30 cut). Decode audio if needed."""
    ffmpeg = get_settings().ffmpeg
    header = 0.0
    completed = _popen([ffmpeg, "-hide_banner", "-i", str(path)], cwd=ROOT)
    match = _DURATION_RE.search(completed.stderr or "")
    if match:
        hours, minutes, seconds = match.groups()
        header = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    decoded = 0.0
    suffix = Path(path).suffix.lower()
    if suffix in {".mp3", ".wav", ".m4a", ".aac", ".ogg"}:
        null = _popen(
            [ffmpeg, "-hide_banner", "-i", str(path), "-f", "null", "-"],
            cwd=ROOT,
        )
        times = _TIME_RE.findall(null.stderr or "")
        if times:
            hours, minutes, seconds = times[-1]
            decoded = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    # Trust the decode. A long fake MP3 header made 10m films go quiet at ~5m.
    if decoded > 0.4:
        if header > 0 and abs(header - decoded) > 1.5:
            log.info("duration header {:.1f}s vs decode {:.1f}s — using decode", header, decoded)
        return decoded
    return header


def compose_video(
    *,
    clips: list[MediaClip],
    audio_path: Path,
    script: VideoScript,
    params: VideoParams,
    subtitles: SubtitleTrack | None,
    workdir: Path,
    output: Path,
    on_progress: ProgressCb | None = None,
) -> Path:
    settings = get_settings()
    ffmpeg = settings.ffmpeg
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    width, height = params.size()
    fps = int(settings.video.get("fps") or 30)
    audio_path = Path(audio_path)
    audio_duration = probe_duration(audio_path) or script.estimated_duration()
    if audio_duration < 4:
        audio_duration = max(script.estimated_duration(), 8.0)

    def tick(pct: int, message: str) -> None:
        if on_progress:
            on_progress(pct, message)

    tick(75, "Normalizing footage")
    # Cover the whole voice with unique stills. Old 48–80s cap looped 4 dull frames for 5 min.
    unique_budget = float(audio_duration)
    prepared = _prepare_clips(
        clips, params, unique_budget, workdir / "norm", width, height, fps, ffmpeg
    )
    if not prepared:
        tick(76, "Building fallback footage")
        prepared = [_synthetic_clip(workdir / "norm" / "fallback.mp4", width, height, unique_budget, fps, ffmpeg)]

    concat_path = workdir / "concat.mp4"
    tick(80, "Cutting the timeline")
    try:
        _concat(
            prepared,
            concat_path,
            ffmpeg,
            params.transition if audio_duration <= 90 else "none",
            float(settings.video.get("fade_duration") or 0.35),
            fps,
        )
    except Exception as exc:
        log.warning("concat failed ({}), using first clip", exc)
        shutil.copy2(prepared[0], concat_path)

    tape_dur = probe_duration(concat_path) or unique_budget
    if tape_dur + 0.4 < audio_duration:
        tick(82, "Looping B-roll to match the voice")
        looped = workdir / "looped.mp4"
        try:
            _loop_tape(concat_path, looped, audio_duration, ffmpeg)
            concat_path = looped
        except Exception as exc:
            log.warning("loop tape failed: {}", exc)

    mixed = workdir / "mixed.mp4"
    tick(85, "Mixing voice and score")
    bgm = _pick_bgm(params, settings)
    try:
        _mix_audio(concat_path, audio_path, bgm, mixed, audio_duration, settings, ffmpeg)
    except Exception as exc:
        log.warning("mix failed ({}), trying simple mux", exc)
        try:
            _simple_mux(concat_path, audio_path, mixed, audio_duration, ffmpeg)
        except Exception as exc2:
            log.warning("simple mux failed ({}), copying picture lock", exc2)
            shutil.copy2(concat_path, mixed)

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    tick(88, "Finishing picture and captions")
    _finish(mixed, output, subtitles, params, settings, ffmpeg, width, height, workdir, audio_duration)

    if output.exists() and output.stat().st_size >= 1024:
        try:
            tick(90, "Channel cards")
            _wrap_channel(output, script, params, workdir, width, height, fps, ffmpeg)
        except Exception as exc:
            log.warning("channel wrap skipped: {}", exc)

    if not output.exists() or output.stat().st_size < 1024:
        for candidate in (mixed, concat_path):
            if candidate.exists() and candidate.stat().st_size >= 1024:
                shutil.copy2(candidate, output)
                break
    if not output.exists() or output.stat().st_size < 1024:
        _emergency_export(output, audio_path, audio_duration, width, height, fps, ffmpeg)
    if not output.exists() or output.stat().st_size < 1024:
        raise RenderError("Renderer produced an empty video.", stage="render")
    tick(92, "Picture lock")
    return output


def export_companion(source: Path, dest: Path, src_size: tuple[int, int], ffmpeg: str) -> Path | None:
    """Second aspect from the finished MP4 — no second full render."""
    source = Path(source)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    w, h = src_size
    portrait = h > w
    if portrait:
        vf = (
            "split[a][b];"
            "[a]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,boxblur=24:8[bg];"
            "[b]scale=-2:1080[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2"
        )
    else:
        vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    cmd = [
        ffmpeg, "-y", "-i", str(source),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-c:a", "aac", "-movflags", "+faststart",
        str(dest),
    ]
    try:
        _run(cmd, "companion-aspect")
        if dest.exists() and dest.stat().st_size >= 1024:
            log.info("Companion export {}", dest.name)
            return dest
    except Exception as exc:
        log.warning("companion export failed: {}", exc)
    return None


def make_thumbnail(video_path: Path, dest: Path, timestamp: float = 1.2) -> Path:
    settings = get_settings()
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        settings.ffmpeg,
        "-y",
        "-ss",
        f"{max(0.1, timestamp):.2f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-q:v",
        "3",
        str(dest),
    ]
    try:
        _run(cmd, "thumbnail")
    except RenderError:
        cmd = [
            settings.ffmpeg,
            "-y",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "4",
            str(dest),
        ]
        _run(cmd, "thumbnail-first")
    return dest


def find_task_video(task_id: str) -> Path | None:
    """Locate a rendered MP4 even if the task record is incomplete."""
    settings = get_settings()
    videos = settings.files.videos
    matches = sorted(videos.glob(f"{task_id}*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if matches:
        return matches[0]
    work = settings.files.task_dir(task_id)
    for name in ("final.mp4", "mixed.mp4", "concat.mp4"):
        candidate = work / name
        if candidate.exists() and candidate.stat().st_size >= 1024:
            return candidate
    leftovers = sorted(work.glob("*.mp4"), key=lambda p: p.stat().st_size, reverse=True)
    return leftovers[0] if leftovers else None


def _prepare_clips(
    clips: list[MediaClip],
    params: VideoParams,
    target: float,
    folder: Path,
    width: int,
    height: int,
    fps: int,
    ffmpeg: str,
) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    vmin = float(settings.video.get("clip_min_duration") or 2.5)
    vmax = float(settings.video.get("clip_max_duration") or 5.5)
    ordered = [clip for clip in clips if clip and Path(clip.path).exists()]
    if not ordered:
        return []
    n_src = max(1, len(ordered))
    if target > 90:
        # Prefer more cuts over looping the same 6 stills for 10 minutes.
        vmin = max(3.6, min(7.0, target / max(n_src, 16)))
        vmax = min(12.0, max(vmin + 1.5, target / max(n_src, 10)))
    grade = _grade_filter(params.color_grade or str(settings.video.get("color_grade") or "cinematic"))
    if (params.concat_mode or "sequential") == "random":
        random.shuffle(ordered)

    prepared: list[Path] = []
    covered = 0.0
    index = 0
    safety = 0
    while covered < target - 0.15 and safety < 200:
        safety += 1
        clip = ordered[index % len(ordered)]
        index += 1
        remaining = target - covered
        length = min(vmax, max(vmin, remaining if remaining < vmax else random.uniform(vmin, vmax)))
        dest = folder / f"clip_{len(prepared):03d}.mp4"
        try:
            _normalize_clip(clip, dest, width, height, fps, length, grade, ffmpeg, variant=index)
            actual = probe_duration(dest) or length
            prepared.append(dest)
            covered += actual
        except Exception as exc:
            log.warning("Skipping clip {}: {}", clip.path, exc)
            try:
                _normalize_clip(clip, dest, width, height, fps, length, "", ffmpeg, simple=True)
                actual = probe_duration(dest) or length
                prepared.append(dest)
                covered += actual
            except Exception as exc2:
                log.warning("Simple normalize also failed: {}", exc2)
                if index > len(ordered) * 4:
                    break
    return prepared


def _normalize_clip(
    clip: MediaClip,
    dest: Path,
    width: int,
    height: int,
    fps: int,
    length: float,
    grade: str,
    ffmpeg: str,
    simple: bool = False,
    variant: int = 0,
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    vf_core = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps={fps}"
    if grade and not simple:
        vf_core = f"{vf_core},{grade}"
    common_out = ["-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(dest)]
    src = Path(clip.path)
    is_image = clip.kind == "image" or src.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    if is_image:
        if not simple:
            frames = max(int(length * fps), fps)
            kind = int(variant) % 4
            if kind == 0:
                zexpr = "min(zoom+0.0015,1.18)"
                xy = "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            elif kind == 1:
                zexpr = "min(zoom+0.0011,1.14)"
                xy = "x='(iw-iw/zoom)*0.15':y='ih/2-(ih/zoom/2)'"
            elif kind == 2:
                zexpr = "min(zoom+0.0011,1.14)"
                xy = "x='(iw-iw/zoom)*0.85':y='ih/2-(ih/zoom/2)'"
            else:
                zexpr = "min(zoom+0.0009,1.10)"
                xy = "x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*0.2'"
            zoom = (
                f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,"
                f"crop={width * 2}:{height * 2},"
                f"zoompan=z='{zexpr}':d={frames}:{xy}:s={width}x{height}:fps={fps}"
            )
            if grade:
                zoom = f"{zoom},{grade}"
            cmd = [ffmpeg, "-y", "-loop", "1", "-i", str(src), "-t", f"{length:.3f}", "-vf", zoom, *common_out]
            try:
                _run(cmd, f"normalize {src.name}")
                return
            except RenderError as exc:
                log.warning("zoompan failed ({}), using still loop", exc)
        cmd = [
            ffmpeg, "-y", "-loop", "1", "-i", str(src), "-t", f"{length:.3f}",
            "-vf", vf_core, *common_out,
        ]
        _run(cmd, f"normalize-still {src.name}")
        return

    src_duration = probe_duration(src) or max(length, 3.0)
    start = 0.0
    if src_duration > length + 0.8:
        start = random.uniform(0.0, max(0.0, src_duration - length - 0.2))
    cmd = [
        ffmpeg, "-y",
        "-ss", f"{start:.3f}",
        "-t", f"{length:.3f}",
        "-i", str(src),
        "-vf", vf_core,
        *common_out,
    ]
    _run(cmd, f"normalize {src.name}")


def _concat(clips: list[Path], dest: Path, ffmpeg: str, transition: str, fade: float, fps: int) -> None:
    if len(clips) == 1:
        shutil.copy2(clips[0], dest)
        return
    if transition == "fade" and 1 < len(clips) <= 10:
        try:
            _concat_xfade(clips, dest, ffmpeg, fade, fps)
            return
        except Exception as exc:
            log.warning("xfade failed ({}), using hard cuts", exc)
    list_file = dest.with_suffix(".txt")
    lines = []
    for path in clips:
        rel = Path(os.path.relpath(path, list_file.parent)).as_posix().replace("'", r"'\''")
        lines.append(f"file '{rel}'")
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(dest)]
    try:
        _run(cmd, "concat", cwd=list_file.parent)
    except RenderError:
        cmd = [
            ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-an", str(dest),
        ]
        _run(cmd, "concat-reencode", cwd=list_file.parent)


def _concat_xfade(clips: list[Path], dest: Path, ffmpeg: str, fade: float, fps: int) -> None:
    durations = [probe_duration(path) or 3.0 for path in clips]
    inputs: list[str] = []
    for path in clips:
        inputs.extend(["-i", str(path)])
    filters = []
    last = "0:v"
    offset = durations[0] - fade
    for index in range(1, len(clips)):
        label = f"v{index}"
        filters.append(
            f"[{last}][{index}:v]xfade=transition=fade:duration={fade:.3f}:offset={max(0.1, offset):.3f}[{label}]"
        )
        last = label
        offset = offset + durations[index] - fade
    graph = ";".join(filters)
    cmd = [
        ffmpeg, "-y", *inputs, "-filter_complex", graph, "-map", f"[{last}]",
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(dest),
    ]
    _run(cmd, "xfade")


def _mix_audio(
    video: Path,
    voice: Path,
    bgm: Path | None,
    dest: Path,
    duration: float,
    settings,
    ffmpeg: str,
) -> None:
    voice_vol = float(settings.audio.get("voice_volume") or 1.0)
    bgm_vol = float(settings.audio.get("bgm_volume") or 0.14)
    fade_in = float(settings.audio.get("fade_in") or 0.4)
    fade_out = float(settings.audio.get("fade_out") or 0.8)
    if bgm and Path(bgm).exists() and bool(settings.audio.get("bgm_enabled", True)):
        filt = (
            f"[1:a]volume={voice_vol},afade=t=in:st=0:d={fade_in},afade=t=out:st={max(0.2, duration - fade_out):.2f}:d={fade_out}[a1];"
            f"[2:a]volume={bgm_vol},aloop=loop=-1:size=2e+09,atrim=0:{duration:.3f},afade=t=in:st=0:d=1,afade=t=out:st={max(0.2, duration - 1.2):.2f}:d=1.2[a2];"
            f"[a1][a2]amix=inputs=2:duration=first:dropout_transition=2,alimiter=limit=0.95[a]"
        )
        cmd = [
            ffmpeg, "-y",
            "-i", str(video),
            "-i", str(voice),
            "-i", str(bgm),
            "-filter_complex", filt,
            "-map", "0:v:0",
            "-map", "[a]",
            "-t", f"{duration:.3f}",
            "-shortest",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", str(settings.video.get("audio_bitrate") or "192k"),
            str(dest),
        ]
        try:
            _run(cmd, "mix audio")
            return
        except RenderError as exc:
            log.warning("bgm mix failed ({}), voice only", exc)
    _mix_voice_only(video, voice, dest, duration, voice_vol, fade_in, fade_out, settings, ffmpeg)


def _mix_voice_only(video, voice, dest, duration, voice_vol, fade_in, fade_out, settings, ffmpeg) -> None:
    filt = f"[1:a]volume={voice_vol},afade=t=in:st=0:d={fade_in},afade=t=out:st={max(0.2, duration - fade_out):.2f}:d={fade_out}[a]"
    cmd = [
        ffmpeg, "-y",
        "-i", str(video),
        "-i", str(voice),
        "-filter_complex", filt,
        "-map", "0:v:0",
        "-map", "[a]",
        "-t", f"{duration:.3f}",
        "-shortest",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", str(settings.video.get("audio_bitrate") or "192k"),
        str(dest),
    ]
    _run(cmd, "mix voice")


def _simple_mux(video: Path, voice: Path, dest: Path, duration: float, ffmpeg: str) -> None:
    cmd = [
        ffmpeg, "-y",
        "-i", str(video),
        "-i", str(voice),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-t", f"{duration:.3f}",
        "-shortest",
        "-c:v", "copy",
        "-c:a", "aac",
        str(dest),
    ]
    _run(cmd, "simple mux")


def _filter_path(path: Path) -> str:
    """Legacy helper — prefer simple relative names instead."""
    path = Path(path).resolve()
    try:
        return path.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        text = path.as_posix().replace("\\", "/")
        if len(text) >= 2 and text[1] == ":":
            text = text[0] + r"\:" + text[2:]
        return text.replace("'", r"\'")


def _copy_simple(src: Path, dest_dir: Path, name: str) -> Path:
    dest = dest_dir / name
    dest_dir.mkdir(parents=True, exist_ok=True)
    if Path(src).resolve() != dest.resolve():
        shutil.copy2(src, dest)
    return dest


def _loop_tape(tape: Path, dest: Path, duration: float, ffmpeg: str) -> Path:
    """Repeat a short B-roll tape with stream copy until it covers the voice."""
    tape_dur = probe_duration(tape) or 8.0
    repeats = max(2, int(duration / max(tape_dur, 1.0)) + 1)
    listing = dest.with_suffix(".txt")
    rel = Path(os.path.relpath(tape, listing.parent)).as_posix().replace("'", r"'\''")
    listing.write_text(("file '%s'\n" % rel) * repeats, encoding="utf-8")
    cmd = [
        ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
        "-t", f"{duration:.3f}", "-c", "copy", str(dest),
    ]
    try:
        _run(cmd, "loop-tape", cwd=listing.parent)
    except RenderError:
        cmd = [
            ffmpeg, "-y", "-stream_loop", "-1", "-i", str(tape),
            "-t", f"{duration:.3f}", "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            str(dest),
        ]
        _run(cmd, "loop-reencode")
    return dest


def _finish(
    source: Path,
    dest: Path,
    subtitles: SubtitleTrack | None,
    params: VideoParams,
    settings,
    ffmpeg: str,
    width: int,
    height: int,
    workdir: Path,
    duration: float = 0.0,
) -> None:
    """Export the final MP4. Captions never block a downloadable file."""
    workdir = Path(workdir)
    source = Path(source)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    want_subs = bool(subtitles and params.subtitle_enabled)
    strategies: list[tuple[str, list[str]]] = []
    long_form = duration > 600

    if want_subs:
        ass_src = Path(subtitles.ass_path) if subtitles.ass_path else None
        srt_src = Path(subtitles.srt_path) if subtitles.srt_path else None
        if ass_src and ass_src.exists():
            _copy_simple(ass_src, workdir, "burn.ass")
            strategies.append(("ass", ["-vf", "ass=burn.ass"]))
            font_dir = workdir / "fonts"
            font_dir.mkdir(exist_ok=True)
            bundled = settings.files.fonts
            if bundled.exists():
                for font in list(bundled.glob("*.ttf")) + list(bundled.glob("*.otf")):
                    target = font_dir / font.name
                    if not target.exists():
                        try:
                            shutil.copy2(font, target)
                        except OSError:
                            pass
            if any(font_dir.iterdir()):
                strategies.append(("ass-fonts", ["-vf", "ass=burn.ass:fontsdir=fonts"]))
        if srt_src and srt_src.exists():
            _copy_simple(srt_src, workdir, "burn.srt")
            from app.services.subtitle import caption_palette, _ass_color

            fill, stroke, _pop = caption_palette(str(params.topic or dest.name))
            style = (
                f"FontName=Arial,FontSize=22,PrimaryColour={_ass_color(fill)},"
                f"OutlineColour={_ass_color(stroke)},BorderStyle=1,Outline=4,Shadow=1,"
                "Alignment=2,MarginV=90,Bold=1"
            )
            strategies.insert(0, ("srt", ["-vf", f"subtitles=burn.srt:force_style='{style}'"]))
            if (workdir / "fonts").exists():
                strategies.insert(
                    1,
                    ("srt-fonts", ["-vf", f"subtitles=burn.srt:fontsdir=fonts:force_style='{style}'"]),
                )
        draw_file = _write_drawtext_script(subtitles, workdir, settings, width, height)
        if draw_file is not None:
            strategies.append(("drawtext", ["-filter_script:v", draw_file.name]))
    elif want_subs and long_form and subtitles and subtitles.srt_path and Path(subtitles.srt_path).exists():
        _copy_simple(Path(subtitles.srt_path), workdir, "burn.srt")

    if params.watermark or bool(settings.video.get("watermark")):
        try:
            from app.services.channel import brand_label

            label = brand_label()
        except Exception:
            label = str(settings.video.get("watermark_text") or "kingscottishDEV")
        safe = re.sub(r"[^A-Za-z0-9 ._-]+", "", label)[:28] or "kingscottishDEV"
        strategies.insert(
            0,
            (
                "watermark",
                ["-vf", f"drawtext=text='{safe}':fontcolor=white@0.22:fontsize=16:x=w-tw-28:y=h-th-28"],
            ),
        )

    encode = [
        "-c:v", "libx264",
        "-preset", str(settings.video.get("preset") or "veryfast"),
        "-crf", str(settings.video.get("crf") or 20),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", str(settings.video.get("audio_bitrate") or "192k"),
        "-movflags", "+faststart",
        str(dest),
    ]

    for name, vf in strategies:
        cmd = [ffmpeg, "-y", "-i", str(source), *vf, *encode]
        try:
            _run(cmd, f"finish-{name}", cwd=workdir)
            if dest.exists() and dest.stat().st_size >= 1024:
                log.info("finish succeeded with {}", name)
                _try_soft_subs(dest, workdir, ffmpeg)
                return
        except RenderError as exc:
            log.warning("finish-{} failed: {}", name, exc)
            if dest.exists():
                try:
                    dest.unlink()
                except OSError:
                    pass

    # Always export a playable file — captions are optional.
    fallback = [ffmpeg, "-y", "-i", str(source), "-c", "copy", "-movflags", "+faststart", str(dest)]
    try:
        _run(fallback, "finish-nosubs")
    except RenderError:
        fallback = [ffmpeg, "-y", "-i", str(source), "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(dest)]
        _run(fallback, "finish-reencode")
    _try_soft_subs(dest, workdir, ffmpeg)


def _write_drawtext_script(track: SubtitleTrack | None, workdir: Path, settings, width: int, height: int) -> Path | None:
    if not track or not track.cues:
        return None
    font = settings.files.font_path(str(settings.subtitle.get("font") or "Montserrat-Bold.ttf"))
    fontfile = ""
    if font.exists():
        fonts_dir = workdir / "fonts"
        fonts_dir.mkdir(exist_ok=True)
        copied = fonts_dir / font.name
        if not copied.exists():
            try:
                shutil.copy2(font, copied)
            except OSError:
                copied = font
        try:
            fontfile = Path(os.path.relpath(copied, workdir)).as_posix()
        except ValueError:
            fontfile = ""
    size = max(18, int(int(settings.subtitle.get("font_size") or 28) * width / 1080))
    position = str(settings.subtitle.get("position") or "bottom")
    if position == "top":
        y_expr = "80"
    elif position == "center":
        y_expr = "(h-text_h)/2"
    else:
        y_expr = "h-text_h-140"
    parts: list[str] = []
    for cue in track.cues[:400]:
        text = _drawtext_escape(cue.text[:80])
        if not text:
            continue
        enable = f"between(t,{cue.start:.3f},{max(cue.end, cue.start + 0.4):.3f})"
        chunk = (
            f"drawtext=text='{text}':fontsize={size}:fontcolor=white:borderw=4:"
            f"bordercolor=black:x=(w-text_w)/2:y={y_expr}:enable='{enable}'"
        )
        if fontfile:
            chunk = f"drawtext=fontfile={fontfile}:text='{text}':fontsize={size}:fontcolor=white:borderw=4:bordercolor=black:x=(w-text_w)/2:y={y_expr}:enable='{enable}'"
        parts.append(chunk)
    if not parts:
        return None
    dest = workdir / "drawtext.flt"
    dest.write_text(",\n".join(parts) + "\n", encoding="utf-8")
    return dest


def _drawtext_escape(text: str) -> str:
    cleaned = " ".join((text or "").split())
    return (
        cleaned.replace("\\", "\\\\")
        .replace("'", "\u2019")
        .replace(":", "\\:")
        .replace("%", "\\%")
        .replace("[", "\\[")
        .replace("]", "\\]")
    )


def _try_soft_subs(video: Path, workdir: Path, ffmpeg: str) -> None:
    """Mux SRT as a movable subtitle track so the file still has captions if burn failed."""
    srt = workdir / "burn.srt"
    if not srt.exists() or not video.exists():
        return
    tmp = video.with_suffix(".soft.mp4")
    cmd = [
        ffmpeg, "-y",
        "-i", str(video),
        "-i", str(srt),
        "-c", "copy",
        "-c:s", "mov_text",
        "-metadata:s:s:0", "language=eng",
        str(tmp),
    ]
    try:
        _run(cmd, "soft-subs")
        if tmp.exists() and tmp.stat().st_size >= video.stat().st_size * 0.8:
            tmp.replace(video)
        elif tmp.exists():
            tmp.unlink(missing_ok=True)
    except RenderError:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _pick_bgm(params: VideoParams, settings) -> Path | None:
    if not params.bgm_enabled:
        return None
    if params.bgm_path and Path(params.bgm_path).exists():
        return Path(params.bgm_path)
    songs = settings.files.list_songs()
    if not songs:
        return None
    wavs = [path for path in songs if path.suffix.lower() in {".wav", ".m4a", ".aac"}]
    return random.choice(wavs or songs)


def _grade_filter(name: str) -> str:
    name = (name or "none").lower()
    if name == "cinematic":
        return "eq=contrast=1.08:saturation=0.88:brightness=0.015"
    if name == "vivid":
        return "eq=contrast=1.12:saturation=1.25:brightness=0.02"
    if name == "moody":
        return "eq=contrast=1.15:saturation=0.7:brightness=-0.04"
    return ""


def _wrap_channel(
    video: Path,
    script: VideoScript,
    params: VideoParams,
    workdir: Path,
    width: int,
    height: int,
    fps: int,
    ffmpeg: str,
) -> None:
    """Stick a title card on the front and a CTA on the tail. Fail-soft."""
    from app.services.cards import paint_card
    from app.services.channel import brand_label, cta_line, load_channel

    ch = load_channel()
    want_intro = bool(getattr(params, "intro_enabled", True) and ch.get("intro_enabled", True))
    want_cta = bool(getattr(params, "cta_enabled", True) and ch.get("cta_enabled", True))
    if not want_intro and not want_cta:
        return
    brand = brand_label()
    pieces: list[Path] = []
    if want_intro:
        still = workdir / "intro.jpg"
        paint_card(
            still,
            kicker=brand,
            headline=script.hook or script.title or params.topic,
            footer=str(ch.get("handle") or brand),
            size=(width, height),
        )
        intro_len = 0.85 if getattr(params, "hook_lock", True) else 2.2
        kicker = brand
        if getattr(params, "series_name", None):
            from app.services.series import series_label

            kicker = series_label(params.series_name, params.series_part, params.series_total) or brand
        paint_card(
            still,
            kicker=kicker,
            headline=script.hook or script.title or params.topic,
            footer=str(ch.get("handle") or brand),
            size=(width, height),
        )
        intro = _card_clip(still, workdir / "intro.mp4", intro_len, width, height, fps, ffmpeg)
        if intro:
            pieces.append(intro)
    pieces.append(video)
    if want_cta:
        still = workdir / "cta.jpg"
        paint_card(
            still,
            kicker=brand,
            headline=cta_line(),
            footer=str(ch.get("handle") or brand),
            size=(width, height),
        )
        cta = _card_clip(still, workdir / "cta.mp4", 2.6, width, height, fps, ffmpeg)
        if cta:
            pieces.append(cta)
    if len(pieces) < 2:
        return
    wrapped = workdir / "channel.mp4"
    listing = workdir / "channel.txt"
    lines = []
    for path in pieces:
        rel = Path(os.path.relpath(path, listing.parent)).as_posix().replace("'", r"'\''")
        lines.append(f"file '{rel}'")
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
    cmd = [
        ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-c:a", "aac", "-movflags", "+faststart",
        str(wrapped),
    ]
    _run(cmd, "channel-concat", cwd=listing.parent)
    if wrapped.exists() and wrapped.stat().st_size >= 1024:
        shutil.copy2(wrapped, video)


def _card_clip(image: Path, dest: Path, length: float, width: int, height: int, fps: int, ffmpeg: str) -> Path | None:
    if not Path(image).exists():
        return None
    cmd = [
        ffmpeg, "-y",
        "-loop", "1", "-i", str(image),
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-t", f"{length:.2f}",
        "-vf", f"scale={width}:{height},fps={fps},format=yuv420p",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-c:a", "aac", "-shortest",
        str(dest),
    ]
    try:
        _run(cmd, f"card {dest.name}")
        return dest if dest.exists() and dest.stat().st_size > 1000 else None
    except Exception as exc:
        log.warning("card clip failed: {}", exc)
        return None


def _synthetic_clip(dest: Path, width: int, height: int, length: float, fps: int, ffmpeg: str, color: str = "0x0c1018") -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    vf = f"format=yuv420p,fps={fps}"
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi",
        "-i", f"color=c={color}:s={width}x{height}:d={max(length, 2.0):.3f}:r={fps}",
        "-vf", vf,
        "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        str(dest),
    ]
    _run(cmd, "synthetic clip")
    return dest


def _emergency_export(dest: Path, audio: Path, duration: float, width: int, height: int, fps: int, ffmpeg: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi",
        "-i", f"color=c=0x0b0e14:s={width}x{height}:d={max(duration, 4.0):.3f}:r={fps}",
        "-i", str(audio),
        "-map", "0:v:0",
        "-map", "1:a:0?",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-c:a", "aac",
        "-shortest",
        "-pix_fmt", "yuv420p",
        str(dest),
    ]
    _run(cmd, "emergency export")


def _popen(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    kwargs: dict = {
        "capture_output": True,
        "text": True,
        "cwd": str(cwd or ROOT),
    }
    if os.name == "nt" and _CREATE_NO_WINDOW:
        kwargs["creationflags"] = _CREATE_NO_WINDOW
    return subprocess.run(cmd, **kwargs)


def _run(cmd: list[str], stage: str, cwd: Path | None = None) -> None:
    log.debug("ffmpeg {}: {}", stage, " ".join(shlex.quote(part) for part in cmd))
    completed = _popen(cmd, cwd=cwd)
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "")[-1200:]
        raise RenderError(f"FFmpeg {stage} failed: {tail}", stage="render")
