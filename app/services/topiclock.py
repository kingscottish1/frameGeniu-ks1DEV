"""Keep research and narration on the user's subject.

Wikipedia / DDG will happily hand back a footballer who shares a first
name or a city. The writer then pads a long film with that bio. This
module is the gate: drop footballer pages when the topic is not football,
and keep the real subject even if that subject happens to be a player.
"""

from __future__ import annotations

import re

_TOKEN = re.compile(r"[a-z0-9]{3,}")
_PAREN = re.compile(r"\(([^)]+)\)")
_SPACE = re.compile(r"\s+")
_NAME = re.compile(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})+\b")

# Place names that match too many wiki pages if treated as identity.
GENERIC = {
    "liverpool",
    "london",
    "manchester",
    "birmingham",
    "leeds",
    "glasgow",
    "edinburgh",
    "dublin",
    "newcastle",
    "sheffield",
    "bristol",
    "cardiff",
    "belfast",
    "city",
    "town",
    "county",
    "england",
    "scotland",
    "wales",
    "ireland",
    "britain",
    "british",
    "united",
    "kingdom",
    "news",
    "wikipedia",
    "the",
    "and",
    "for",
    "from",
    "with",
    "about",
    "who",
    "was",
    "his",
    "her",
    "their",
}

# Association-football fingerprint. UK wiki search leans on this hard.
FOOTBALL = (
    "footballer",
    "football player",
    "soccer player",
    "association football",
    "midfielder",
    "winger",
    "goalkeeper",
    "centre-back",
    "center-back",
    "centre back",
    "full-back",
    "full back",
    "sweeper",
    "playmaker",
    "premier league",
    "la liga",
    "bundesliga",
    "serie a",
    "ligue 1",
    "champions league",
    "europa league",
    "conference league",
    "fa cup",
    "efl cup",
    "carabao cup",
    "fifa world cup",
    "football club",
    "youth academy",
    "transfer fee",
    "transfer window",
    "loaned to",
    "international caps",
    "first-team debut",
    "first team debut",
    "made his debut for",
    "made her debut for",
    "goals in all competitions",
    "appearances for",
    "played as a forward",
    "played as a midfielder",
    "played as a defender",
    "played as a striker",
    "played as a winger",
    "scottish premiership",
    "english football league",
)

FOOTBALL_TITLE = (
    "footballer",
    "football player",
    "soccer player",
    "soccer",
    "football club",
    " f.c.",
    " f.c",
    " afc",
    " a.f.c",
    "premier league",
)

FOOTBALL_TOPIC = (
    "football",
    "footballer",
    "soccer",
    "premier league",
    "fifa",
    "uefa",
    " f.c",
    " fc ",
    "la liga",
    "bundesliga",
    "champions league",
    "world cup",
    "striker",
    "midfielder",
    "goalkeeper",
    "epl",
    "fa cup",
    "liverpool fc",
    "manchester united",
    "manchester city",
    "real madrid",
    "barcelona",
)


def _norm(text: str) -> str:
    return _SPACE.sub(" ", (text or "").strip())


def tokens(text: str) -> list[str]:
    return _TOKEN.findall((text or "").lower())


# Common words that are in the topic but do not identify it.
# "nicole blaine killer" must match Nicole/Blaine, not every "killer" story.
WEAK = {
    "killer", "killers", "murder", "murderer", "murders", "crime", "criminal",
    "case", "trial", "court", "news", "story", "history", "life", "death",
    "dead", "police", "victim", "suspect", "arrest", "man", "woman", "girl",
    "boy", "people", "person", "true", "deep", "dive", "film", "video",
}


def distinctive(topic: str) -> list[str]:
    toks = [t for t in tokens(topic) if t not in GENERIC]
    strong = [t for t in toks if t not in WEAK]
    return strong or toks


def on_subject(text: str, topic: str, *, min_hits: int | None = None) -> bool:
    """True when the text actually names the user's subject."""
    dist = distinctive(topic)
    if not dist:
        return True
    low = f" {(text or '').lower()} "
    hits = sum(1 for t in dist if f" {t} " in low)
    need = min_hits if min_hits is not None else (2 if len(dist) >= 2 else 1)
    return hits >= need


def is_football_topic(topic: str) -> bool:
    low = f" {(topic or '').lower()} "
    if any(k in low for k in FOOTBALL_TOPIC):
        return True
    # "Liverpool F.C." / "Arsenal FC"
    if re.search(r"\b[a-z]{2,}\s+f\.?c\.?\b", low):
        return True
    return False


def football_hits(text: str) -> int:
    low = f" {(text or '').lower()} "
    return sum(1 for marker in FOOTBALL if marker in low)


def football_heavy(text: str) -> bool:
    """Two+ football markers → this is a player bio, not a passing mention."""
    return football_hits(text) >= 2


def _bare_title(title: str) -> str:
    return _PAREN.sub(" ", title or "").strip()


def title_is_the_subject(title: str, topic: str) -> bool:
    """True when the wiki title *is* the thing the user typed."""
    t = _bare_title(title).lower()
    q = (topic or "").strip().lower()
    if not t or not q:
        return False
    if t == q or t.startswith(q) or q.startswith(t):
        return True
    dist = distinctive(topic)
    if len(dist) >= 2 and all(tok in t for tok in dist):
        return True
    return False


def football_title(title: str) -> bool:
    low = f" {(title or '').lower()} "
    if any(bit in low for bit in FOOTBALL_TITLE):
        return True
    disc = _PAREN.search(title or "")
    if disc:
        d = disc.group(1).lower()
        if any(bit in d for bit in ("footballer", "football player", "soccer", "football")):
            return True
    if re.search(r"\bf\.?c\.?\b", low):
        return True
    return False


def score_title(title: str, topic: str, snippet: str = "") -> int:
    hay = f"{title} {snippet}".lower()
    dist = distinctive(topic)
    toks = tokens(topic)
    dist_hits = sum(1 for t in dist if t in hay)
    tok_hits = sum(1 for t in toks if t in hay)
    score = dist_hits * 12 + tok_hits * 2
    if title_is_the_subject(title, topic):
        score += 30
    if not is_football_topic(topic) and football_title(title) and not title_is_the_subject(title, topic):
        score -= 100
    if not is_football_topic(topic) and football_heavy(snippet) and not title_is_the_subject(title, topic):
        score -= 40
    return score


def rank_titles(topic: str, titles: list[str], snippets: list[str] | None = None) -> list[str]:
    snips = list(snippets or [])
    scored: list[tuple[int, str]] = []
    for i, title in enumerate(titles):
        if not title:
            continue
        snip = snips[i] if i < len(snips) else ""
        scored.append((score_title(title, topic, snip), title))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    keep: list[str] = []
    seen: set[str] = set()
    for score, title in scored:
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        if not title_is_the_subject(title, topic) and score < 8:
            continue
        keep.append(title)
    return keep


def keep_page(extract: str, topic: str, title: str = "", anchor: str = "") -> bool:
    """Whether a whole wiki/web page belongs in the research pile."""
    if title_is_the_subject(title, topic):
        return True
    if not is_football_topic(topic):
        if football_title(title):
            return False
        lead = (extract or "")[:2500]
        if football_heavy(lead):
            return False
        if anchor and football_heavy(lead) and not football_heavy(anchor[:2500]):
            return False
    if on_subject(title, topic) or on_subject((extract or "")[:1800], topic):
        return True
    return False


def _same_person(name: str, topic: str) -> bool:
    q = (topic or "").lower()
    low = (name or "").lower()
    if not low or not q:
        return False
    if low in q:
        return True
    parts = low.split()
    if parts[-1] and parts[-1] in q:
        return True
    return all(part in q for part in parts)


def keep_note(text: str, topic: str) -> bool:
    """Whether a fact may go in the chew pile.

    Pages are filtered separately. A sentence from an on-subject article
    does not have to repeat the name every line. A different person's bio
    or a random 'killer' story is still out.
    """
    blob = _norm(text)
    if len(blob) < 12:
        return False
    if on_subject(text, topic):
        if not is_football_topic(topic) and football_heavy(blob) and not on_subject(text, topic, min_hits=1):
            return False
        return True
    if not is_football_topic(topic) and football_heavy(blob):
        return False
    names = _NAME.findall(text or "")
    if names and not any(_same_person(n, topic) for n in names):
        return False
    low = f" {(text or '').lower()} "
    if len(distinctive(topic)) >= 2 and any(f" {w} " in low for w in ("killer", "killers", "murder", "murderer")):
        return False
    return True


_PRONOUN = re.compile(
    r"^(He|She|They|It|His|Her|Their|This|That|Those|These|Then|Later)\b"
)


def strip_off_topic(text: str, topic: str) -> str:
    """Drop off-subject paragraphs from spoken narration."""
    blob = (text or "").strip()
    if not blob:
        return blob
    chunks = re.split(r"\n+", blob)
    kept: list[str] = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        if keep_note(chunk, topic) or on_subject(chunk, topic):
            kept.append(chunk)
            continue
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", chunk) if s.strip()]
        good = [s for s in sents if keep_note(s, topic) or on_subject(s, topic)]
        if good:
            kept.append(" ".join(good))
    return "\n\n".join(kept).strip()


def unused_notes(notes: str, already: str) -> str:
    """Notes the voiceover has not already spoken — still on-topic leftovers."""
    if not notes:
        return ""
    hay = (already or "").lower()
    out: list[str] = []
    for line in notes.splitlines():
        body = line.lstrip("- ").strip()
        if not body:
            continue
        words = body.lower().split()
        key = " ".join(words[:8])
        if len(key) >= 12 and key in hay:
            continue
        # Six-word fingerprint — catch paraphrased repeats, not just the first clause.
        if len(words) >= 6:
            mark = " ".join(words[:6])
            if mark in hay:
                continue
        out.append(line if line.startswith("- ") else "- " + body)
    return "\n".join(out)


_GLUE = ("sub and follow",)


def allowed_names(topic: str, research=None, spoken: str = "") -> set[str]:
    """Tokens the narration is allowed to keep using."""
    names = set(distinctive(topic))
    if research is not None:
        for item in list(getattr(research, "people", None) or []) + list(getattr(research, "places", None) or []):
            for tok in tokens(str(item)):
                if tok not in GENERIC and len(tok) >= 3:
                    names.add(tok)
        for fact in list(getattr(research, "facts", None) or [])[:12]:
            for n in _NAME.findall(str(fact)):
                for tok in tokens(n):
                    if tok not in GENERIC and len(tok) >= 4:
                        names.add(tok)
    for n in _NAME.findall(spoken or ""):
        for tok in tokens(n):
            if tok not in GENERIC and len(tok) >= 4:
                names.add(tok)
    return names


def same_story(text: str, topic: str, allowed: set[str] | None = None) -> bool:
    """True when this sentence is still about the user's subject."""
    blob = _norm(text)
    if len(blob) < 8:
        return True
    low = blob.lower()
    if any(g in low for g in _GLUE) and len(blob.split()) < 10:
        return True
    if _PRONOUN.match((text or "").strip()):
        names = _NAME.findall(text or "")
        if names and not any(_same_person(n, topic) for n in names):
            return False
        return True
    if on_subject(text, topic):
        return True
    if not keep_note(text, topic):
        return False
    dist = distinctive(topic)
    allowed = set(allowed or dist)
    hits = sum(1 for t in dist if t in low)
    need = 2 if len(dist) >= 2 else 1
    if dist and hits >= need:
        return True
    for n in _NAME.findall(text or ""):
        if _same_person(n, topic):
            return True
        if not any(tok in allowed for tok in tokens(n)):
            return False
    return False


def lock_narration(text: str, topic: str, allowed: set[str] | None = None) -> str:
    """Drop random detours. Keep pronoun follow-ups of an on-subject line."""
    blob = strip_off_topic(text or "", topic)
    if not blob:
        return ""
    allowed = allowed or allowed_names(topic, spoken=blob[:2000])
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", blob) if s.strip()]
    kept: list[str] = []
    on = False
    for sent in sents:
        ok = same_story(sent, topic, allowed)
        if not ok and on and _PRONOUN.match(sent) and not _NAME.findall(sent):
            ok = True
        if ok:
            kept.append(sent)
            on = True
            for n in _NAME.findall(sent):
                for tok in tokens(n):
                    if tok not in GENERIC and len(tok) >= 4:
                        allowed.add(tok)
        else:
            on = False
    return " ".join(kept).strip()
