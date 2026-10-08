"""Bleep profanity in a spoken track. Never kill the rest of the sound."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from app.config.settings import get_settings
from app.models.audio import WordTiming
from app.utils.logger import get_logger

log = get_logger("bleep")

_EXACT = {
    "fuck", "fucking", "fucked", "fucker", "fuckers", "motherfucker", "motherfuckers",
    "shit", "shits", "shitty", "bullshit", "horseshit",
    "bitch", "bitches", "bitching",
    "cunt", "cunts",
    "asshole", "assholes",
    "bastard", "bastards",
    "dickhead", "dickheads",
    "piss", "pissed", "pissing",
    "cocksucker",
    "pussy", "pussies",
    "slut", "sluts",
    "whore", "whores",
    "wanker", "wankers",
    "twat", "twats",
    "bollocks",
    "prick", "pricks",
    "douche", "douchebag",
    "goddamn", "goddamnit", "goddam",
    "motherfucking",
    "nigger", "niggers", "nigga", "niggas",
    "faggot", "faggots",
    "retard", "retarded",
}
# Prefixes only — never 'cock'/'ass' as a stem (cocktail, class, assess).
_STEMS = ("fuck", "motherfuck", "shit", "bitch", "cunt", "asshole", "nigger", "nigga", "faggot")
_TOKEN = re.compile(r"[a-z0-9']+")
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def _norm_word(word: str) -> str:
    return _TOKEN.findall((word or "").lower().replace("’", "'"))[0] if _TOKEN.search(word or "") else ""


def is_profane(word: str) -> bool:
    token = _norm_word(word)
    if not token:
        return False
    if token in _EXACT:
        return True
    if token in {"ass", "arse"}:
        return True
    return any(token.startswith(stem) and len(token) >= len(stem) for stem in _STEMS)


def profane_ranges(words: list[WordTiming], *, pad: float = 0.06) -> list[tuple[float, float]]:
    hits: list[tuple[float, float]] = []
    for item in words or []:
        if not is_profane(item.word):
            continue
        start = max(0.0, float(item.start) - pad)
        end = max(start + 0.12, float(item.end) + pad)
        hits.append((start, end))
    if not hits:
        return []
    hits.sort()
    merged = [hits[0]]
    for start, end in hits[1:]:
        prev_s, prev_e = merged[-1]
        if start <= prev_e + 0.04:
            merged[-1] = (prev_s, max(prev_e, end))
        else:
            merged.append((start, end))
    return merged


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    kwargs: dict = {"capture_output": True, "text": True}
    if _CREATE_NO_WINDOW:
        kwargs["creationflags"] = _CREATE_NO_WINDOW
    return subprocess.run(cmd, **kwargs)


def _copy(src: Path, dest: Path) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != dest.resolve():
        dest.write_bytes(Path(src).read_bytes())
    return dest


def bleep_audio(src: Path, dest: Path, ranges: list[tuple[float, float]], duration: float) -> Path:
    """Punch a beep over swear windows only. On any failure, keep the original track."""
    src = Path(src)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not src.exists() or src.stat().st_size < 64:
        return dest
    if not ranges:
        return _copy(src, dest)

    covered = sum(max(0.0, b - a) for a, b in ranges)
    dur = max(float(duration or 0), 1.0)
    if covered > dur * 0.25:
        log.warning("bleep would wipe {:.0f}% of the track — keeping original audio", 100 * covered / dur)
        return _copy(src, dest)

    ffmpeg = get_settings().ffmpeg
    hit = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in ranges[:120])
    # eval=frame is mandatory. eval=once mutes the WHOLE file if t=0 is inside a hit.
    filt = (
        f"[0:a]volume=eval=frame:volume='if({hit},0,1)'[a];"
        f"sine=frequency=1000:sample_rate=44100:duration={dur:.3f}[s];"
        f"[s]volume=eval=frame:volume='if({hit},0.4,0)'[b];"
        f"[a][b]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[out]"
    )
    out_try = dest.with_suffix(".bleep" + dest.suffix)
    cmd = [
        ffmpeg, "-y", "-i", str(src),
        "-filter_complex", filt, "-map", "[out]",
        "-c:a", "aac", "-b:a", "192k",
        str(out_try),
    ]
    completed = _run(cmd)
    if completed.returncode != 0 or not out_try.exists() or out_try.stat().st_size < 64:
        log.warning("bleep mix failed ({}) — keeping original sound", (completed.stderr or "")[-400:])
        out_try.unlink(missing_ok=True)
        return _copy(src, dest)
    out_try.replace(dest)
    log.info("Bleeped {} hits, rest of the soundtrack kept", len(ranges))
    return dest
