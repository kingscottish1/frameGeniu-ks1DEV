"""Subtitle generation — TTS timings stretched to the real voice bed."""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.config.settings import get_settings
from app.models.audio import WordTiming
from app.models.script import VideoScript
from app.models.subtitle import SubtitleCue, SubtitleTrack
from app.utils.logger import get_logger
from app.utils.validators import hex_color

log = get_logger("subtitle")

# Captions must sit long enough to read. 5 words flashing every 0.8s is the "too fast" bug.
MIN_CUE = 3.4
MAX_CUE = 7.0
MIN_WORDS = 8
DEFAULT_WORDS = 12


def _caption_pace(audio_duration: float) -> tuple[float, float, int, int]:
    """min_cue, max_cue, words_per_line, min_words — matched to this film's length."""
    d = max(8.0, float(audio_duration or 30))
    if d <= 45:
        return 2.0, 4.2, 7, 5
    if d <= 90:
        return 2.6, 5.2, 9, 6
    if d <= 400:
        return 3.4, 6.5, 12, 8
    return 4.0, 7.5, 14, 10


def build_subtitles(
    script: VideoScript,
    *,
    words: list[WordTiming] | None = None,
    audio_path: str | Path | None = None,
    duration: float = 0.0,
    workdir: Path,
    theme=None,
    seed: str = "",
) -> SubtitleTrack:
    settings = get_settings()
    cfg = settings.subtitle
    provider = str(cfg.get("provider") or "edge").lower()
    audio_duration = float(duration or 0.0)
    if audio_duration <= 0 and audio_path:
        try:
            from app.services.video import probe_duration

            audio_duration = probe_duration(audio_path) or 0.0
        except Exception:
            audio_duration = 0.0
    if audio_duration <= 0:
        audio_duration = script.estimated_duration() or 8.0

    min_cue, max_cue, pace_words, min_words = _caption_pace(audio_duration)
    cfg_words = int(cfg.get("words_per_line") or 0)
    per_line = max(pace_words, cfg_words) if cfg_words >= 12 else pace_words

    aligned = _align_words(list(words or []), audio_duration)

    cues: list[SubtitleCue] = []
    if aligned:
        cues = _from_words(aligned, per_line, min_cue=min_cue, max_cue=max_cue, min_words=min_words)
    elif provider == "whisper" and audio_path:
        cues = _from_whisper(Path(audio_path), per_line)
    if not cues:
        cues = _from_script(script, audio_duration, per_line, cue_seconds=min_cue)

    cues = _fit_cues(cues, audio_duration)

    track = SubtitleTrack(cues=cues, language=script.language)
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    srt_path = workdir / "subtitles.srt"
    ass_path = workdir / "subtitles.ass"
    srt_path.write_text(track.to_srt(), encoding="utf-8")
    track.srt_path = str(srt_path)
    try:
        ass_path.write_text(render_ass(track, settings, theme=theme, seed=seed), encoding="utf-8")
        track.ass_path = str(ass_path)
    except TypeError:
        # Older render_ass(track, settings) — never kill the film over captions.
        ass_path.write_text(render_ass(track, settings), encoding="utf-8")
        track.ass_path = str(ass_path)
    except Exception as exc:
        log.warning("ASS write failed ({}), SRT only — editor will still export", exc)
    return track


def _align_words(words: list[WordTiming], duration: float) -> list[WordTiming]:
    """If Edge word clocks finish early, stretch them to the real MP3 length."""
    cleaned = [w for w in words if w and (w.word or "").strip()]
    if not cleaned or duration <= 1.0:
        return cleaned
    last = max(float(w.end) for w in cleaned)
    if last <= 0.4:
        return cleaned
    scale = duration / last
    if abs(scale - 1.0) < 0.04:
        return cleaned
    log.info("caption clock {:.1f}s vs voice {:.1f}s — stretching x{:.3f}", last, duration, scale)
    out: list[WordTiming] = []
    for w in cleaned:
        out.append(WordTiming(word=w.word, start=float(w.start) * scale, end=float(w.end) * scale))
    return out


def _from_words(
    words: list[WordTiming],
    per_line: int,
    *,
    min_cue: float | None = None,
    max_cue: float | None = None,
    min_words: int | None = None,
) -> list[SubtitleCue]:
    """Hold a line until it is readable. Never split on commas. Pace follows the film."""
    if not words:
        return []
    min_cue = float(min_cue if min_cue is not None else MIN_CUE)
    max_cue = float(max_cue if max_cue is not None else MAX_CUE)
    min_words = int(min_words if min_words is not None else MIN_WORDS)
    per_line = max(int(per_line or DEFAULT_WORDS), min_words)
    cues: list[SubtitleCue] = []
    index = 1
    i = 0
    n = len(words)
    while i < n:
        start = float(words[i].start)
        j = i
        while j < n:
            end = float(words[j].end)
            count = j - i + 1
            dur = max(0.0, end - start)
            token = (words[j].word or "").rstrip()
            ended = token.endswith((".", "!", "?"))
            take = False
            if count >= per_line and dur >= min_cue and (ended or count >= per_line + 2 or dur >= min_cue + 0.4):
                take = True
            elif ended and count >= min_words and dur >= min_cue:
                take = True
            elif dur >= max_cue and count >= 4:
                take = True
            elif j == n - 1:
                take = True
            if take:
                j += 1
                break
            j += 1
        bucket = words[i:j]
        if not bucket:
            break
        text = " ".join((w.word or "").strip() for w in bucket if (w.word or "").strip())
        cue_start = float(bucket[0].start)
        cue_end = max(float(bucket[-1].end), cue_start + min_cue)
        if j < n:
            nxt = float(words[j].start)
            if nxt > cue_start + 0.9:
                cue_end = min(cue_end, nxt)
        if cue_end <= cue_start:
            cue_end = cue_start + min_cue
        cues.append(
            SubtitleCue(
                index=index,
                start=cue_start,
                end=cue_end,
                text=text,
                words=[(w.word or "").strip() for w in bucket],
            )
        )
        index += 1
        i = j
    return _merge_short(cues)


def _merge_short(cues: list[SubtitleCue]) -> list[SubtitleCue]:
    if len(cues) < 2:
        return cues
    out: list[SubtitleCue] = []
    for cue in cues:
        if out and (cue.end - cue.start) < 1.5 and (out[-1].end - out[-1].start) < MAX_CUE:
            prev = out[-1]
            merged_text = (prev.text + " " + cue.text).strip()
            out[-1] = SubtitleCue(
                index=prev.index,
                start=prev.start,
                end=max(cue.end, prev.start + MIN_CUE),
                # MIN_CUE here is a floor; merge already happened because cue was short
                text=merged_text,
                words=(prev.words or []) + (cue.words or []),
            )
        else:
            out.append(cue)
    for i, cue in enumerate(out, start=1):
        cue.index = i
    return out


def _fit_cues(cues: list[SubtitleCue], duration: float) -> list[SubtitleCue]:
    """Keep the last caption on screen until the voice actually ends."""
    if not cues or duration <= 0:
        return cues
    last = float(cues[-1].end or 0.0)
    if last <= 0.2:
        return cues
    scale = duration / last
    if abs(scale - 1.0) >= 0.04:
        fitted: list[SubtitleCue] = []
        for cue in cues:
            fitted.append(
                SubtitleCue(
                    index=cue.index,
                    start=float(cue.start) * scale,
                    end=float(cue.end) * scale,
                    text=cue.text,
                    words=list(cue.words or []),
                )
            )
        cues = fitted
    # no overlaps, last cue rides to the end of the voice
    cleaned: list[SubtitleCue] = []
    for i, cue in enumerate(cues):
        start = max(0.0, float(cue.start))
        end = max(start + 0.8, float(cue.end))
        if i + 1 < len(cues):
            nxt = float(cues[i + 1].start)
            if nxt > start + 0.6:
                end = min(end, nxt)
        cleaned.append(
            SubtitleCue(index=i + 1, start=start, end=end, text=cue.text, words=list(cue.words or []))
        )
    if cleaned:
        cleaned[-1] = SubtitleCue(
            index=cleaned[-1].index,
            start=cleaned[-1].start,
            end=max(cleaned[-1].end, duration),
            text=cleaned[-1].text,
            words=list(cleaned[-1].words or []),
        )
    return cleaned


def _from_script(script: VideoScript, duration: float, per_line: int, cue_seconds: float = 4.0) -> list[SubtitleCue]:
    """Even split across the REAL voice length — not compressed scene caps."""
    text = script.narration
    tokens = [t for t in text.split() if t]
    if not tokens:
        return []
    total = max(float(duration), 1.0)
    chunk = max(6, int(per_line or DEFAULT_WORDS))
    hold = max(2.0, float(cue_seconds or 4.0))
    target_cues = max(1, int(round(total / hold)))
    chunk = max(chunk, max(1, int(round(len(tokens) / target_cues))))
    groups = [tokens[i : i + chunk] for i in range(0, len(tokens), chunk)]
    n = len(groups)
    slice_len = total / n
    return [
        SubtitleCue(
            index=i + 1,
            start=i * slice_len,
            end=(i + 1) * slice_len,
            text=" ".join(group),
            words=group,
        )
        for i, group in enumerate(groups)
    ]


def _from_whisper(audio_path: Path, per_line: int) -> list[SubtitleCue]:
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:
        log.warning("faster-whisper is not installed: {}", exc)
        return []
    settings = get_settings()
    cfg = settings.section("whisper")
    device = str(cfg.get("device") or "auto")
    if device == "auto":
        device = "cpu"
    try:
        model = WhisperModel(
            str(cfg.get("model_size") or "base"),
            device=device,
            compute_type=str(cfg.get("compute_type") or "int8"),
            download_root=str(cfg.get("download_root") or "models"),
        )
        segments, _info = model.transcribe(str(audio_path), vad_filter=bool(cfg.get("vad_filter", True)), word_timestamps=True)
    except Exception as exc:
        log.warning("Whisper transcription failed: {}", exc)
        return []
    words: list[WordTiming] = []
    for segment in segments:
        for word in getattr(segment, "words", None) or []:
            words.append(WordTiming(word=word.word.strip(), start=float(word.start), end=float(word.end)))
    return _from_words(words, per_line)


def caption_palette(seed: str) -> tuple[str, str, str]:
    """Fresh fill / stroke / pop colour per film. Always readable."""
    palettes = (
        ("#FFFFFF", "#000000", "#FF2A2A"),
        ("#FFF8E7", "#140800", "#FFB000"),
        ("#F4F1EA", "#0A0A0A", "#E8B923"),
        ("#F5FBFF", "#001018", "#3EE0FF"),
        ("#FFE8F4", "#1A0510", "#FF5AA5"),
        ("#F2FFE8", "#06140A", "#7CFF4D"),
        ("#FFFFFF", "#1A0000", "#FF6B35"),
        ("#FFF4D6", "#0A0800", "#FFD60A"),
    )
    digest = int(hashlib.sha1((seed or "fg").encode("utf-8")).hexdigest()[:8], 16)
    return palettes[digest % len(palettes)]


def render_ass(track: SubtitleTrack, settings, theme=None, seed: str = "") -> str:
    cfg = settings.subtitle
    video = settings.video
    width = int(video.get("width") or 1080)
    height = int(video.get("height") or 1920)
    font_name = "Arial"
    size = max(22, min(36, int(cfg.get("font_size") or 28)))
    fill, stroke, pop = caption_palette(seed or str(getattr(theme, "id", "") or "fg"))
    primary_hex = _theme_value(theme, "font_color", fill)
    outline_hex = _theme_value(theme, "stroke_color", stroke)
    highlight_hex = _theme_value(theme, "highlight", pop)
    if seed:
        primary_hex, outline_hex, highlight_hex = fill, stroke, pop
    primary = _ass_color(hex_color(primary_hex))
    outline = _ass_color(hex_color(outline_hex))
    highlight = _ass_color(hex_color(highlight_hex))
    position = str(cfg.get("position") or "bottom")
    alignment = {"top": 8, "center": 5, "bottom": 2}.get(position, 2)
    margin_v = 160 if position == "bottom" else 80
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{size},{primary},{highlight},{outline},&H80000000,-1,0,0,0,100,100,0,0,1,{int(cfg.get('stroke_width') or 3)},1,{alignment},80,80,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for cue in track.cues:
        text = cue.text.replace("\n", r"\N").replace("{", "(").replace("}", ")")
        events.append(f"Dialogue: 0,{_ass_ts(cue.start)},{_ass_ts(cue.end)},Default,,0,0,0,,{text}")
    return header + "\n".join(events) + "\n"


def _ass_ts(seconds: float) -> str:
    millis = int(round(max(0.0, seconds) * 100))
    hours, rem = divmod(millis, 360000)
    minutes, rem = divmod(rem, 6000)
    secs, cs = divmod(rem, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def _ass_color(hex_value: str) -> str:
    text = hex_value.lstrip("#")
    if len(text) >= 6:
        r, g, b = text[0:2], text[2:4], text[4:6]
        return f"&H00{b}{g}{r}".upper()
    return "&H00FFFFFF"


def _theme_value(theme, attr: str, fallback: str) -> str:
    if theme is None:
        return fallback
    if isinstance(theme, dict):
        value = theme.get(attr) or theme.get("highlight_color" if attr == "highlight" else attr)
    else:
        value = getattr(theme, attr, None)
    text = str(value or "").strip()
    return text or fallback
