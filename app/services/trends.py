"""Free trend radar — no signup, no Reddit (they 403).

Wikipedia most-viewed + Hacker News + DuckDuckGo HTML, then studio fallbacks.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import quote

import httpx

from app.utils.logger import get_logger

log = get_logger("trends")

UA = "FrameGenius/1.7 (local studio; kingscottishDEV N.A.S)"
HEADERS = {"User-Agent": UA, "Accept": "application/json,text/html;q=0.9", "Accept-Language": "en"}

NICHE_QUERIES = {
    "crime": ["true crime news", "unsolved case", "cartel investigation"],
    "news": ["world news today", "breaking geopolitics"],
    "gym": ["strength training", "powerlifting news"],
    "story": ["today in history", "forgotten documentary story"],
    "entertainment": ["viral culture story", "film news today"],
    "all": ["today in history", "world news today", "true crime"],
}

CRIME_HINT = ("murder", "kill", "crime", "police", "trial", "prison", "mafia", "cartel", "kingpin", "case")
GYM_HINT = ("gym", "lift", "fitness", "athlete", "workout", "bodybuild")
NEWS_HINT = ("war", "election", "president", "market", "israel", "ukraine", "china", "minister")
STORY_HINT = ("history", "ancient", "discovered", "lost", "ship", "museum")

SKIP_TITLES = {
    "main page",
    "special:search",
    "special:createaccount",
    "wikipedia",
    "wikimedia",
    "portal:current events",
}

FALLBACK = {
    "crime": [
        "The Black Dahlia file they never closed",
        "How the Kinahan cartel moved through Europe",
        "The night D.B. Cooper walked off the plane",
        "Oak Island: the money pit that never pays",
    ],
    "news": [
        "The story behind this week's market shock",
        "What the latest election numbers actually mean",
        "A war you stopped seeing on the homepage",
    ],
    "gym": [
        "The 5am deadlift rule nobody wants to hear",
        "Why most people stall at the same lift",
        "Build a back that looks like it works",
    ],
    "story": [
        "The library fire that saved a city",
        "A ship that vanished with the tide tables",
        "The last telegram that changed a war",
    ],
    "entertainment": [
        "Why this one clip broke the timeline",
        "The forgotten sequel that should have won",
        "A concert that never officially happened",
    ],
}


def fetch_trends(niche: str = "all", limit: int = 12) -> list[dict]:
    key = (niche or "all").lower()
    if key not in NICHE_QUERIES:
        key = "all"
    bag: list[dict] = []
    with httpx.Client(headers=HEADERS, timeout=12.0, follow_redirects=True) as client:
        bag.extend(_wikipedia_most(client))
        bag.extend(_hacker_news(client))
        for query in NICHE_QUERIES[key][:2]:
            bag.extend(_duckduckgo(client, query, key))
    cleaned = _dedupe(bag, key, limit)
    if len(cleaned) < 4:
        for title in FALLBACK.get(key, FALLBACK["story"]):
            if not any(title.lower() == (item.get("title") or "").lower() for item in cleaned):
                cleaned.append({"title": title, "source": "studio", "url": "", "niche": key})
    return cleaned[:limit]


def _wikipedia_most(client: httpx.Client) -> list[dict]:
    try:
        resp = client.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "query", "list": "mostviewed", "pvimlimit": 30, "format": "json"},
        )
        if resp.status_code >= 400:
            return []
        rows = ((resp.json() or {}).get("query") or {}).get("mostviewed") or []
    except Exception as exc:
        log.debug("wiki mostviewed skipped: {}", exc)
        return []
    out: list[dict] = []
    for row in rows:
        title = _clean(str(row.get("title") or ""))
        if not title or title.lower() in SKIP_TITLES or title.lower().startswith("special:"):
            continue
        if int(row.get("ns") or 0) != 0:
            continue
        slug = title.replace(" ", "_")
        out.append(
            {
                "title": title[:140],
                "source": "Wikipedia",
                "url": f"https://en.wikipedia.org/wiki/{quote(slug)}",
                "niche": _guess_niche(title),
            }
        )
    return out


def _hacker_news(client: httpx.Client) -> list[dict]:
    try:
        ids = client.get("https://hacker-news.firebaseio.com/v0/topstories.json").json()[:18]
    except Exception as exc:
        log.debug("hn list skipped: {}", exc)
        return []
    out: list[dict] = []
    for hid in ids:
        try:
            item = client.get(f"https://hacker-news.firebaseio.com/v0/item/{hid}.json").json() or {}
        except Exception:
            continue
        title = _clean(str(item.get("title") or ""))
        if len(title) < 12:
            continue
        out.append(
            {
                "title": title[:140],
                "source": "HN",
                "url": str(item.get("url") or f"https://news.ycombinator.com/item?id={hid}"),
                "niche": _guess_niche(title),
            }
        )
    return out


class _DDGParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.titles: list[str] = []
        self._grab = False
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        cls = attrs_d.get("class", "")
        if tag == "a" and ("result__a" in cls or attrs_d.get("rel") == "nofollow"):
            self._grab = True
            self._buf = []

    def handle_endtag(self, tag):
        if tag == "a" and self._grab:
            title = _clean(" ".join(self._buf))
            if title:
                self.titles.append(title)
            self._grab = False

    def handle_data(self, data):
        if self._grab:
            self._buf.append(data)


def _duckduckgo(client: httpx.Client, query: str, niche: str) -> list[dict]:
    try:
        resp = client.get(
            f"https://html.duckduckgo.com/html/?q={quote(query)}",
            headers={**HEADERS, "Accept": "text/html"},
        )
        if resp.status_code >= 400:
            return []
        parser = _DDGParser()
        parser.feed(resp.text)
    except Exception as exc:
        log.debug("ddg trends skipped: {}", exc)
        return []
    out: list[dict] = []
    for title in parser.titles[:8]:
        if len(title) < 12:
            continue
        out.append({"title": title[:140], "source": "web", "url": "", "niche": niche})
    return out


def _guess_niche(title: str) -> str:
    low = (title or "").lower()
    if any(w in low for w in CRIME_HINT):
        return "crime"
    if any(w in low for w in GYM_HINT):
        return "gym"
    if any(w in low for w in NEWS_HINT):
        return "news"
    if any(w in low for w in STORY_HINT):
        return "story"
    return "all"


def _dedupe(items: list[dict], niche: str, limit: int) -> list[dict]:
    seen: set[str] = set()
    preferred: list[dict] = []
    rest: list[dict] = []
    for item in items:
        title = _clean(item.get("title") or "")
        if len(title) < 12:
            continue
        slug = title.lower()
        if slug in seen:
            continue
        seen.add(slug)
        row = {**item, "title": title}
        if niche == "all" or row.get("niche") == niche or _guess_niche(title) == niche:
            preferred.append(row)
        else:
            rest.append(row)
    return (preferred + rest)[:limit]


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    text = re.sub(r"^\[.*?\]\s*", "", text)
    return text[:140]
