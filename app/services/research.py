"""Public-web research — Wikipedia, DuckDuckGo, and page extracts. No API key."""

from __future__ import annotations

import html
import json
import re
import time
from html.parser import HTMLParser
from urllib.parse import quote, unquote, urlparse

import httpx

from app.models.research import ResearchBrief, Source
from app.services.topiclock import keep_note, keep_page, rank_titles
from app.utils.logger import get_logger

log = get_logger("research")

UA = "FrameGenius/1.5 (local video studio by kingscottishDEV N.A.S; +https://github.com/kingscottishDEV/FrameGenius)"
HEADERS = {"User-Agent": UA, "Accept": "application/json,text/html;q=0.9", "Accept-Language": "en"}
TIMEOUT = 20.0

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_SENT_RE = re.compile(r"(?<=[.!?])\s+")
_DATE_RE = re.compile(r"\b(?:(?:19|20)\d{2}|[A-Z][a-z]+ \d{1,2}, (?:19|20)\d{2})\b")


class _DDGParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[tuple[str, str, str]] = []
        self._href = ""
        self._title_parts: list[str] = []
        self._snip_parts: list[str] = []
        self._in_title = False
        self._in_snip = False

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        cls = attrs_d.get("class", "")
        if tag == "a" and "result__a" in cls:
            self._href = attrs_d.get("href") or ""
            self._in_title = True
            self._title_parts = []
        elif tag == "a" and attrs_d.get("rel") == "nofollow" and not self._href:
            href = attrs_d.get("href") or ""
            if href.startswith("http"):
                self._href = href
                self._in_title = True
                self._title_parts = []
        elif "result__snippet" in cls or "result-snippet" in cls:
            self._in_snip = True
            self._snip_parts = []

    def handle_endtag(self, tag):
        if tag == "a" and self._in_title:
            self._in_title = False
        if tag in {"a", "td", "div"} and self._in_snip:
            self._in_snip = False
            self._flush()

    def handle_data(self, data):
        if self._in_title:
            self._title_parts.append(data)
        elif self._in_snip:
            self._snip_parts.append(data)

    def _flush(self):
        title = _clean(" ".join(self._title_parts))
        snip = _clean(" ".join(self._snip_parts))
        url = _unwrap_ddg(self._href)
        if url and title:
            self.results.append((title, url, snip))
        self._href = ""
        self._title_parts = []
        self._snip_parts = []


def research_topic(topic: str, *, max_pages: int = 8, min_words: int = 0) -> ResearchBrief:
    topic = (topic or "").strip()
    brief = ResearchBrief(topic=topic)
    if len(topic) < 2:
        return brief
    want = max(0, int(min_words or 0))
    with httpx.Client(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
        wiki_titles = 6 if want >= 4000 else 4
        _wikipedia(client, topic, brief, titles=wiki_titles)
        _duckduckgo(client, topic, brief)
        extra_q = [
            f'"{topic}"',
            f"{topic} timeline",
            f"{topic} explained",
            f"{topic} history",
            f"who is {topic}",
            f"{topic} what happened",
            f"{topic} aftermath",
        ]
        cap = 18 if want >= 8000 else 12
        for query in extra_q:
            if len(brief.sources) >= cap:
                break
            _duckduckgo(client, query, brief)
        _fetch_pages(client, brief, max_pages=max_pages)
    _derive(
        brief,
        fact_limit=600 if want >= 8000 else (200 if want >= 4000 else 80),
        extract_limit=80 if want >= 8000 else (40 if want >= 4000 else 16),
    )
    words = sum(len((e or "").split()) for e in brief.extracts) + sum(len((f or "").split()) for f in brief.facts)
    log.info(
        "Research '{}': {} sources, {} facts, {} extracts, ~{} words",
        topic,
        len(brief.sources),
        len(brief.facts),
        len(brief.extracts),
        words,
    )
    return brief


def _wikipedia(client: httpx.Client, topic: str, brief: ResearchBrief, titles: int = 4) -> None:
    found, urls = _wiki_search(client, topic)
    if not found:
        found, urls = [topic], [""]
    # Search a few candidates, keep only pages that are actually this subject.
    take = max(3, min(6, int(titles or 4)))
    kept = 0
    anchor = ""

    for title, url in zip(found[:take], (urls or [""] * len(found))[:take]):
        if kept >= take:
            break
        time.sleep(0.4)
        extract = ""
        lead_image = ""
        page_url = url or f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
        # MediaWiki action=query only — REST is blocked on many networks.
        try:
            resp = _wiki_get(
                client,
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "prop": "extracts|pageimages",
                    "explaintext": 1,
                    "exsectionformat": "plain",
                    "piprop": "original",
                    "titles": title,
                    "format": "json",
                    "redirects": 1,
                    "origin": "*",
                },
            )
            pages = ((resp or {}).get("query") or {}).get("pages") or {}
            for page in pages.values():
                extract = _clean(str(page.get("extract") or extract))
                orig = page.get("original") or {}
                lead_image = str(orig.get("source") or lead_image)
                title = str(page.get("title") or title)
        except Exception as exc:
            log.warning("Wikipedia extract failed for {}: {}", title, exc)
        if not extract:
            extract = _wiki_html(client, title)
        if not extract:
            continue
        if not keep_page(extract, topic, title=title, anchor=anchor):
            log.info("Skip off-topic wiki '{}' for '{}'", title, topic)
            continue
        brief.sources.append(Source(title=title, url=page_url, snippet=extract[:280]))
        if not brief.summary:
            brief.summary = extract[:600]
            anchor = extract[:4000]
        brief.extracts.append(extract[:60000])
        for sent in _sentences(extract)[:120]:
            if 40 < len(sent) < 400 and keep_note(sent, topic):
                brief.facts.append(sent)
        if lead_image:
            brief.image_urls.append(lead_image)
        _wiki_media(client, title, brief)
        kept += 1


def _wiki_search(client: httpx.Client, topic: str) -> tuple[list[str], list[str]]:
    # list=search is more stable than opensearch on some networks.
    try:
        data = _wiki_get(
            client,
            "https://en.wikipedia.org/w/api.php",
            params={"action": "query", "list": "search", "srsearch": topic, "srlimit": 15, "format": "json", "utf8": 1},
        )
        hits = ((data or {}).get("query") or {}).get("search") or []
        raw_titles = [str(item.get("title") or "") for item in hits if item.get("title")]
        snips = [_clean(_TAG_RE.sub(" ", str(item.get("snippet") or ""))) for item in hits if item.get("title")]
        titles = _rank_titles(topic, raw_titles, snips)
        urls = [f"https://en.wikipedia.org/wiki/{quote(t.replace(' ', '_'))}" for t in titles]
        if titles:
            return titles, urls
    except Exception as exc:
        log.warning("Wikipedia list=search failed: {}", exc)
    try:
        data = _wiki_get(
            client,
            "https://en.wikipedia.org/w/api.php",
            params={"action": "opensearch", "search": topic, "limit": 6, "namespace": 0, "format": "json"},
        )
        if isinstance(data, list) and len(data) >= 4:
            titles = _rank_titles(topic, list(data[1] or []))
            url_map = {str(t): str(u) for t, u in zip(data[1] or [], data[3] or [])}
            return titles, [url_map.get(t, f"https://en.wikipedia.org/wiki/{quote(t.replace(' ', '_'))}") for t in titles]
    except Exception as exc:
        log.warning("Wikipedia opensearch failed: {}", exc)
    return [], []


def _rank_titles(topic: str, titles: list[str], snippets: list[str] | None = None) -> list[str]:
    return rank_titles(topic, titles, snippets)


def _wiki_html(client: httpx.Client, title: str) -> str:
    try:
        resp = client.get(
            f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}",
            headers={**HEADERS, "Accept": "text/html"},
        )
        if resp.status_code >= 400:
            return ""
        return _html_to_text(resp.text)[:40000]
    except Exception as exc:
        log.warning("Wikipedia HTML failed for {}: {}", title, exc)
        return ""


def _wiki_media(client: httpx.Client, title: str, brief: ResearchBrief) -> None:
    try:
        data = _wiki_get(
            client,
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "titles": title,
                "generator": "images",
                "gimlimit": 8,
                "prop": "imageinfo",
                "iiprop": "url|mime",
                "iiurlwidth": 1280,
                "format": "json",
                "origin": "*",
            },
        )
        pages = ((data or {}).get("query") or {}).get("pages") or {}
        for page in pages.values():
            info = (page.get("imageinfo") or [{}])[0]
            src = info.get("thumburl") or info.get("url") or ""
            mime = str(info.get("mime") or "")
            title_text = str(page.get("title") or src)
            if src and mime.startswith("image/") and _looks_like_photo(src, title_text):
                brief.image_urls.append(src)
    except Exception as exc:
        log.warning("Wikipedia images failed for {}: {}", title, exc)


def _looks_like_photo(url: str, title: str) -> bool:
    hay = f"{url} {title}".lower()
    skip = (".svg", "icon", "logo", "flag_of", "coat_of_arms", "wikimedia-button", "edit-clear")
    return not any(part in hay for part in skip)


def _wiki_get(client: httpx.Client, url: str, params: dict | None = None):
    last = None
    for attempt in range(3):
        try:
            resp = client.get(url, params=params)
            if resp.status_code == 429:
                time.sleep(1.2 * (attempt + 1))
                last = RuntimeError("429")
                continue
            resp.raise_for_status()
            if "json" in (resp.headers.get("content-type") or ""):
                return resp.json()
            return None
        except Exception as exc:
            last = exc
            time.sleep(0.5 * (attempt + 1))
    if last:
        raise last
    return None


def _duckduckgo(client: httpx.Client, query: str, brief: ResearchBrief) -> None:
    seen = {src.url for src in brief.sources}
    for url in (
        f"https://html.duckduckgo.com/html/?q={quote(query)}",
        f"https://lite.duckduckgo.com/lite/?q={quote(query)}",
    ):
        try:
            resp = client.get(url, headers={**HEADERS, "Accept": "text/html"})
            if resp.status_code >= 400:
                continue
            parser = _DDGParser()
            parser.feed(resp.text)
            for title, href, snip in parser.results[:8]:
                if href in seen or _skip_url(href):
                    continue
                if not keep_page(snip or title, brief.topic, title=title):
                    continue
                seen.add(href)
                brief.sources.append(Source(title=title, url=href, snippet=snip))
                if snip and 40 < len(snip) < 280 and keep_note(snip, brief.topic):
                    brief.facts.append(snip)
            if parser.results:
                return
        except Exception as exc:
            log.warning("DuckDuckGo failed ({}): {}", url, exc)
    try:
        resp = client.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
        )
        payload = resp.json()
        abstract = _clean(str(payload.get("AbstractText") or ""))
        heading = str(payload.get("Heading") or query)
        if abstract and keep_page(abstract, brief.topic, title=heading):
            if keep_note(abstract, brief.topic):
                brief.facts.insert(0, abstract)
            if not brief.summary:
                brief.summary = abstract
            src = payload.get("AbstractURL") or ""
            if src:
                brief.sources.append(Source(title=heading, url=src, snippet=abstract[:280]))
        for item in payload.get("RelatedTopics") or []:
            if isinstance(item, dict) and item.get("Text"):
                text = _clean(str(item["Text"]))
                if text and keep_note(text, brief.topic):
                    brief.facts.append(text[:280])
    except Exception as exc:
        log.warning("DuckDuckGo IA failed: {}", exc)


def _fetch_pages(client: httpx.Client, brief: ResearchBrief, *, max_pages: int) -> None:
    count = 0
    for source in list(brief.sources):
        if count >= max_pages:
            break
        if _skip_url(source.url):
            continue
        host = urlparse(source.url).netloc.lower()
        if "wikipedia.org" in host:
            continue
        try:
            resp = client.get(source.url, headers={**HEADERS, "Accept": "text/html"})
            if resp.status_code >= 400 or "text" not in (resp.headers.get("content-type") or ""):
                continue
            text = _html_to_text(resp.text)
            if len(text) < 200:
                continue
            if not keep_page(text[:2500], brief.topic, title=source.title):
                log.info("Skip off-topic page '{}' for '{}'", source.title or source.url, brief.topic)
                continue
            brief.extracts.append(text[:40000])
            for sent in _sentences(text)[:80]:
                if 50 < len(sent) < 400 and keep_note(sent, brief.topic):
                    brief.facts.append(sent)
            count += 1
        except Exception as exc:
            log.warning("Fetch failed {}: {}", source.url, exc)


def _derive(brief: ResearchBrief, *, fact_limit: int = 80, extract_limit: int = 16) -> None:
    from app.services.visuals import named_people, visual_queries

    topic = brief.topic or ""
    brief.facts = [f for f in brief.facts if keep_note(f, topic)]
    brief.extracts = [e for e in brief.extracts if keep_page(e, topic)]
    if brief.summary and not keep_note(brief.summary, topic) and not keep_page(brief.summary, topic):
        brief.summary = ""
    brief.facts = _unique(brief.facts, max(80, int(fact_limit)))
    tokens = [w.lower() for w in re.findall(r"[a-zA-Z]{3,}", topic)]
    if tokens and brief.facts:
        brief.facts.sort(key=lambda fact: -sum(tok in fact.lower() for tok in tokens))
        best = brief.facts[0]
        if sum(tok in (brief.summary or "").lower() for tok in tokens) < sum(tok in best.lower() for tok in tokens):
            brief.summary = best[:600]
    brief.extracts = _unique(brief.extracts, max(16, int(extract_limit)))
    brief.image_urls = _unique(brief.image_urls, 12)
    blob = " ".join(brief.facts[:20] + [brief.summary])
    for match in _DATE_RE.findall(blob):
        if match not in brief.dates:
            brief.dates.append(match)
    brief.people = named_people(blob, brief.topic, limit=8)
    years = [d for d in brief.dates if d.isdigit() and len(d) == 4]
    extra = list(brief.people[:4]) + [f"{brief.topic} {y}" for y in years[:2]]
    brief.queries = visual_queries(brief.topic, extra=extra)
    brief.image_queries = list(brief.queries)
    if not brief.summary and brief.facts:
        brief.summary = brief.facts[0]


def _html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", raw)
    raw = _TAG_RE.sub(" ", raw)
    return _clean(html.unescape(raw))


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENT_RE.split(text) if part.strip()]


def _clean(text: str) -> str:
    return _SPACE_RE.sub(" ", text or "").strip()


def _unique(items: list[str], limit: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = _clean(item)
        low = key.lower()
        if not key or low in seen:
            continue
        seen.add(low)
        out.append(key)
        if len(out) >= limit:
            break
    return out


def _unwrap_ddg(href: str) -> str:
    href = html.unescape(href or "")
    if "uddg=" in href:
        try:
            from urllib.parse import parse_qs, urlparse

            qs = parse_qs(urlparse(href).query)
            if qs.get("uddg"):
                return unquote(qs["uddg"][0])
        except Exception:
            pass
    return href


def _skip_url(url: str) -> bool:
    host = urlparse(url or "").netloc.lower()
    if not host:
        return True
    blocked = ("facebook.com", "instagram.com", "tiktok.com", "x.com", "twitter.com", "reddit.com", "pinterest.")
    return any(part in host for part in blocked)


def brief_to_json(brief: ResearchBrief) -> str:
    return json.dumps(brief.model_dump(), ensure_ascii=False, indent=2)
