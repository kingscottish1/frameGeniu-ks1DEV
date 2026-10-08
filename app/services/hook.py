"""Opening beat — from the subject's own facts, never a canned line."""

from __future__ import annotations

import re

from app.models.script import Scene, VideoScript


def punch_hook(topic: str, research=None) -> str:
    topic = (topic or "").strip()
    if research is not None:
        for block in list(getattr(research, "facts", None) or []) + list(getattr(research, "extracts", None) or []):
            line = _first_clause(block, topic)
            if line:
                return line
        summary = str(getattr(research, "summary", "") or "")
        line = _first_clause(summary, topic)
        if line:
            return line
    if topic:
        return f"{topic}."
    return "Start here."


def lock_opening(script: VideoScript, topic: str, research=None) -> VideoScript:
    """Keep the real opening. Cap it at ~3s. Do not prepend a stock phrase."""
    scenes = list(script.scenes or [])
    punch = punch_hook(topic, research)
    if scenes:
        first = scenes[0].narration.strip()
        if _is_stock(first):
            scenes[0].narration = punch
            scenes[0].search = scenes[0].search or topic
            scenes[0].visual = scenes[0].visual or topic
        scenes[0].duration = min(3.2, max(2.2, min(scenes[0].duration, 3.2)))
        script.scenes = scenes
        script.hook = _first_clause(scenes[0].narration, topic) or punch
    else:
        script.scenes = [Scene(narration=punch, search=topic, visual=topic, duration=2.8)]
        script.hook = punch
    script.raw_text = " ".join(s.narration for s in script.scenes)
    script.apply_timings()
    return script


def apply_series(
    script: VideoScript,
    topic: str,
    name: str,
    part: int | None,
    total: int | None,
) -> VideoScript:
    from app.services.series import recall, recap_line, remember, series_label, tease_line

    name = (name or "").strip()
    if not name:
        return script
    part = int(part or 1)
    total_i = int(total) if total else None
    label = series_label(name, part, total_i)
    if label:
        script.title = label[:90]
    prev = recall(name)
    scenes = list(script.scenes or [])
    if part > 1:
        recap = recap_line(topic, name, part, str(prev.get("hook") or ""))
        scenes.insert(1 if scenes else 0, Scene(narration=recap, search=topic, visual=topic, duration=3.2))
    tease = tease_line(topic, name, part, total_i)
    if not scenes or _norm(scenes[-1].narration) != _norm(tease):
        scenes.append(Scene(narration=tease, search=topic, visual=topic, duration=2.8))
    script.scenes = scenes
    script.raw_text = " ".join(s.narration for s in scenes)
    script.apply_timings()
    remember(name, part, total_i, script.hook, topic)
    return script


def shape_script(
    script: VideoScript,
    topic: str,
    *,
    hook_lock: bool = True,
    series_name: str = "",
    series_part: int | None = None,
    series_total: int | None = None,
    research=None,
) -> VideoScript:
    if hook_lock:
        script = lock_opening(script, topic, research)
    if series_name:
        script = apply_series(script, topic, series_name, series_part, series_total)
    return script


def _first_clause(text: str, topic: str) -> str:
    text = " ".join((text or "").split())
    if not text:
        return ""
    text = re.sub(r"\[[0-9]{1,3}\]", "", text)
    sent = re.split(r"(?<=[.!?])\s+", text)[0].strip()
    if sent.lower().startswith("this article is about") or "may refer to" in sent.lower():
        return ""
    words = sent.split()
    if len(words) > 18:
        sent = " ".join(words[:18]).rstrip(",;:") + "."
    elif sent and sent[-1] not in ".!?":
        sent += "."
    if len(sent) < 20:
        return ""
    return sent


def _is_stock(text: str) -> bool:
    low = (text or "").lower()
    stocks = (
        "they told you",
        "start here. ",
        "if you only know the headline",
        "three things about",
        "nobody starts at the beginning",
        "forget the recap they gave you",
        "nobody is coming to save you",
    )
    return any(s in low for s in stocks)


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())
