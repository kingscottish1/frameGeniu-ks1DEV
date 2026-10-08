"""Keep every B-roll query and downloaded file tied to the topic."""

from __future__ import annotations

import re

MONTHS = {
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
}
GENERIC = {
    "photo", "portrait", "scene", "archive", "map", "historic", "history",
    "the", "this", "that", "when", "after", "from", "they", "with", "about",
    "file", "official", "story", "people", "years", "still", "matter", "names",
    "press", "version", "paper", "trail", "close", "night", "city", "image",
    "picture", "video", "stock", "free", "child", "children", "kid", "kids",
    "dog", "dogs", "cat", "cats", "puppy", "baby", "babies", "family",
}

_TOKEN = re.compile(r"[a-z0-9]{3,}")
_NAME = re.compile(
    r"\b(?!January|February|March|April|May|June|July|August|September|October|November|December)"
    r"([A-Z][a-z]{2,})(?:\s+([A-Z][a-z]{2,}))+\b"
)


def topic_tokens(topic: str) -> list[str]:
    return [w for w in _TOKEN.findall((topic or "").lower()) if w not in MONTHS]


def is_relevant_text(text: str, topic: str) -> bool:
    tokens = topic_tokens(topic)
    if not tokens:
        return True
    hay = (text or "").lower()
    return any(token in hay for token in tokens)


def is_junk_query(query: str) -> bool:
    words = [w for w in _TOKEN.findall((query or "").lower())]
    if not words:
        return True
    if all(w in MONTHS or w in GENERIC for w in words):
        return True
    if words[0] in MONTHS and any(w in {"portrait", "photo", "picture"} for w in words):
        return True
    return False


def sanitize_query(query: str, topic: str) -> str | None:
    q = " ".join((query or "").split())
    if len(q) < 3 or is_junk_query(q):
        return None
    if is_relevant_text(q, topic):
        return q
    return None


def named_people(text: str, topic: str, limit: int = 6) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    blob = f"{topic}. {text or ''}"
    for match in _NAME.finditer(blob):
        name = match.group(0).strip()
        key = name.lower()
        if key in seen or any(part.lower() in MONTHS for part in name.split()):
            continue
        if key == (topic or "").lower() or key.replace("the ", "") == (topic or "").lower().replace("the ", ""):
            continue
        seen.add(key)
        found.append(name)
        if len(found) >= limit:
            break
    return found


def visual_queries(topic: str, *, extra: list[str] | None = None, template: str = "") -> list[str]:
    """Only topic-anchored searches. Never 'January portrait'."""
    topic = (topic or "").strip()
    out: list[str] = []
    seen: set[str] = set()

    def add(item: str | None) -> None:
        if not item:
            return
        clean = sanitize_query(item, topic) or (item if item.lower() == topic.lower() else None)
        if not clean:
            return
        parts = clean.split()
        collapsed: list[str] = []
        for word in parts:
            if collapsed and collapsed[-1].lower() == word.lower():
                continue
            collapsed.append(word)
        clean = " ".join(collapsed)
        key = clean.lower()
        if key in seen or not clean:
            return
        if key == f"{topic.lower()} {topic.lower()}":
            return
        seen.add(key)
        out.append(clean)

    add(topic)
    if template in {"crime", "true-crime", "true_crime", "crime-deep-dive"}:
        add(f"{topic} crime scene")
        add(f"{topic} investigation")
        add(f"{topic} newspaper")
    else:
        add(f"{topic} documentary")
        add(f"{topic} archive photograph")
    for item in extra or []:
        add(item)
        # if a person name, still require the topic nearby for stock search
        if item and item[0].isupper() and " " in item and not is_junk_query(item):
            add(f"{item} {topic}")
    return out[:10]


def generate_prompts(topic: str, template: str, queries: list[str] | None = None) -> list[str]:
    from app.services.theme import shot_prompts

    return shot_prompts(topic, template, limit=8)


def hit_is_relevant(title: str, topic: str) -> bool:
    if is_relevant_text(title, topic):
        return True
    # Commons often titles files with underscores
    return is_relevant_text(title.replace("_", " "), topic)
