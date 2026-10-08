"""Per-film look: shots, grade, caption colours. Crime ≠ gym."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FilmTheme:
    id: str
    grade: str
    font_color: str
    stroke_color: str
    highlight: str
    shots: tuple[str, ...]
    avoid: str = "no children, no kids, no babies, no dogs, no cats, no pets, no cartoon, no text, no watermark"


THEMES: dict[str, FilmTheme] = {
    "crime": FilmTheme(
        id="crime",
        grade="moody",
        font_color="#F4F1EA",
        stroke_color="#0A0A0A",
        highlight="#E8B923",
        shots=(
            "police cruiser at night in the rain, red and blue lights, wet asphalt, cinematic",
            "yellow crime scene tape across a dark alley, film grain",
            "interrogation room, one hanging lamp, empty metal table",
            "stack of case files and a manila folder on a detective desk",
            "empty parking garage fluorescent lights, noir",
            "vintage newspaper printing press, no readable headline",
            "city surveillance camera at night",
            "courtroom empty benches, dramatic light",
        ),
    ),
    "gym": FilmTheme(
        id="gym",
        grade="vivid",
        font_color="#FFFFFF",
        stroke_color="#111111",
        highlight="#FF4D2E",
        shots=(
            "dark gym, barbell on the floor, chalk dust in a shaft of light",
            "close up chalked hands gripping a steel bar",
            "empty squat rack, industrial gym, cinematic",
            "locker room bench, gym bag, moody light",
            "athlete silhouette in a doorway of a gym at dawn",
            "weight plates stacked, dramatic side light",
        ),
    ),
    "news": FilmTheme(
        id="news",
        grade="cinematic",
        font_color="#FFFFFF",
        stroke_color="#000000",
        highlight="#3EE0FF",
        shots=(
            "newsroom monitors glowing at night",
            "city skyline dusk, documentary",
            "satellite dish against a dark sky",
            "stack of newspapers on a desk, no readable text",
        ),
    ),
    "motivational": FilmTheme(
        id="motivational",
        grade="cinematic",
        font_color="#FFF8E7",
        stroke_color="#1A1208",
        highlight="#F0D27A",
        shots=(
            "sunrise over a mountain ridge, lone runner silhouette",
            "empty road at dawn, cinematic wide",
            "ocean horizon long exposure",
            "city from a rooftop at sunrise",
        ),
    ),
    "educational": FilmTheme(
        id="educational",
        grade="cinematic",
        font_color="#FFFFFF",
        stroke_color="#0B1220",
        highlight="#7ED0FF",
        shots=(
            "library aisle warm lamp, documentary",
            "macro of a notebook and pencil",
            "old globe on a wooden desk",
            "chalkboard with faint unreadable marks",
        ),
    ),
    "entertainment": FilmTheme(
        id="entertainment",
        grade="vivid",
        font_color="#FFFFFF",
        stroke_color="#160816",
        highlight="#FF5AA5",
        shots=(
            "neon city night, wet street reflections",
            "cinema seats in the dark, screen glow",
            "concert stage lights bokeh, empty",
        ),
    ),
    "product": FilmTheme(
        id="product",
        grade="cinematic",
        font_color="#F5FBFF",
        stroke_color="#0A1018",
        highlight="#3EE0FF",
        shots=(
            "minimal desk, laptop closed, soft daylight",
            "macro of a clean device on black",
            "workshop tools arranged, cinematic",
        ),
    ),
    "story": FilmTheme(
        id="story",
        grade="moody",
        font_color="#F6EDE3",
        stroke_color="#140E0C",
        highlight="#E0B48A",
        shots=(
            "rain on a window at night, warm interior",
            "empty street at dawn, fog",
            "old notebook on a wooden table",
        ),
    ),
}

_ALIASES = {
    "true-crime": "crime",
    "true_crime": "crime",
    "crime-deep-dive": "crime",
    "crime_deep_dives": "crime",
}

_TOPIC_HINTS = (
    (
        "crime",
        (
            "murder",
            "killer",
            "police",
            "dahlia",
            "crime",
            "detective",
            "prison",
            "mafia",
            "serial",
            "kingpin",
            "cartel",
            "gangster",
            "gangland",
            "mobster",
            "underworld",
            "syndicate",
            "hitman",
            "homicide",
            "assassin",
            "fugitive",
            "traffick",
            "heist",
            "robbery",
            "indictment",
            "drug lord",
            "organized crime",
            "true crime",
            "mob boss",
            "crime family",
            "forensic",
            "cold case",
            "crime scene",
            "kidnap",
            "gunman",
            "interrogat",
            "felon",
            "cartel",
            "narco",
            "cocaine",
            "heroin",
            "kinahan",
            "gotti",
            "escobar",
        ),
    ),
    ("gym", ("gym", "workout", "fitness", "bodybuild", "barbell", "deadlift", "squat", "athlete")),
    ("news", ("news", "election", "market", "headline", "war", "politics")),
    ("motivational", ("motivat", "discipline", "hustle", "grind", "mindset")),
)


def detect_theme(topic: str, template: str = "") -> FilmTheme:
    tmpl = (template or "").lower()
    key = _ALIASES.get(tmpl, tmpl)
    if key in THEMES and tmpl not in {"", "auto"}:
        return THEMES[key]
    blob = (topic or "").lower()
    for name, hints in _TOPIC_HINTS:
        if any(h in blob for h in hints):
            return THEMES[name]
    return THEMES["story"]


def topic_shots(topic: str) -> tuple[str, ...]:
    """Shots built from the topic itself — works for bread, space, boxing, anything."""
    t = (topic or "the subject").strip()
    return (
        f"{t}, cinematic wide establishing shot, photoreal",
        f"{t}, close up documentary detail, shallow depth of field",
        f"{t}, moody archive photograph, no readable text",
        f"{t}, night, film grain, dramatic light",
    )


_ANGLES = (
    "wide establishing shot, photoreal cinematic",
    "close-up documentary detail, shallow depth of field",
    "medium shot, dramatic side light, photoreal",
    "night, film grain, wet surfaces, cinematic",
    "archive still photograph, faded, no readable text",
    "interior, practical lighting, photoreal cinematic",
    "high angle, cinematic composition, photoreal",
    "macro of objects and hands, documentary",
    "empty location after the fact, moody cinematic",
    "street level, photoreal, natural light",
    "golden hour, cinematic still, photoreal",
    "overcast daylight, documentary still",
    "lamplight interior, film still, photoreal",
    "rain, reflections, cinematic photoreal",
    "silhouette against a window, moody photoreal",
    "detail of objects on a table, no readable text, photoreal",
    "doorway, cinematic frame, photoreal",
    "long lens compression, documentary still",
    "blue hour city or landscape, cinematic",
    "harsh overhead light, photoreal still",
)

_STOP = {
    "the", "this", "that", "with", "from", "they", "them", "have", "will", "just",
    "about", "were", "been", "into", "then", "than", "when", "what", "your",
    "their", "there", "would", "could", "should", "because", "sub", "follow",
}


def still_count(duration: float, limit: int = 0) -> int:
    """How many unique stills to paint. 30s→6, 5 min→25. Never starve a film."""
    if limit and int(limit) > 4:
        return max(6, min(28, int(limit)))
    d = float(duration or 30)
    if d <= 40:
        return 8
    if d <= 75:
        return 12
    if d <= 130:
        return 18
    return int(min(48, max(22, round(d / 10.0))))


_SPICES = (
    "teal and orange grade",
    "cool moonlight",
    "warm tungsten interior",
    "harsh fluorescent",
    "fog in the air",
    "golden dust motes",
    "wet asphalt reflections",
    "soft window light",
    "overcast daylight",
    "sodium street lamps",
    "blue hour",
    "hard noon sun",
)


def _beats(topic: str, script=None, research=None) -> list[str]:
    topic = (topic or "").strip()
    seen: set[str] = {topic.lower()} if topic else set()
    out: list[str] = []

    def add(item: str) -> None:
        bit = " ".join(str(item or "").split())
        if len(bit) < 3:
            return
        key = bit.lower()
        if key in seen:
            return
        seen.add(key)
        out.append(bit[:90])

    if script is not None:
        for scene in getattr(script, "scenes", None) or []:
            add(str(getattr(scene, "visual", "") or getattr(scene, "search", "") or ""))
            narr = str(getattr(scene, "narration", "") or "")
            words = [w for w in re.findall(r"[A-Za-z]{3,}", narr) if w.lower() not in _STOP]
            if len(words) >= 3:
                add(" ".join(words[:6]))
    if research is not None:
        for item in list(getattr(research, "people", None) or [])[:8]:
            add(str(item))
        for item in list(getattr(research, "places", None) or [])[:8]:
            add(str(item))
        for fact in list(getattr(research, "facts", None) or [])[:16]:
            words = [w for w in re.findall(r"[A-Za-z]{3,}", str(fact)) if w.lower() not in _STOP]
            if len(words) >= 3:
                add(" ".join(words[:6]))
    return out


def film_stills(topic: str, script=None, research=None, limit: int = 4, duration: float = 30.0, salt: str = "") -> list[str]:
    """Fresh unique stills about THIS subject — enough to cover the picked length."""
    topic = (topic or "").strip()
    n = still_count(duration, limit)
    avoid = (
        "no children, no kids, no text, no letters, no watermark, no logo, "
        "35mm documentary photograph, natural colour, film grain, not CGI, not digital art, photoreal"
    )
    extras = _beats(topic, script, research)
    rng = random.Random(f"{topic}|{salt}|{n}")
    angles = list(_ANGLES)
    spices = list(_SPICES)
    rng.shuffle(angles)
    rng.shuffle(spices)
    out: list[str] = []
    for index in range(n):
        extra = extras[index] if index < len(extras) else (extras[index % len(extras)] if extras else "")
        angle = angles[index % len(angles)]
        spice = spices[index % len(spices)]
        take = f"{(salt or 'x')[:8]}-{index + 1}"
        if extra:
            prompt = f"{topic}, {extra}, {angle}, {spice}, {avoid}, unique take {take}"
        else:
            prompt = f"{topic}, {angle}, {spice}, {avoid}, unique take {take}, related to {topic}"
        out.append(prompt)
    return out


def shot_prompts(topic: str, template: str = "", limit: int = 8, duration: float = 30.0, salt: str = "") -> list[str]:
    return film_stills(topic, limit=limit, duration=duration, salt=salt)
