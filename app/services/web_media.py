"""Download topic-relevant stills and video. Hits must mention the topic."""

from __future__ import annotations

import re
from pathlib import Path

import httpx

from app.providers.media.base import MediaClip
from app.services.visuals import hit_is_relevant
from app.utils.logger import get_logger

log = get_logger("web-media")

UA = "FrameGenius/1.5 (local video studio by kingscottishDEV N.A.S)"
HEADERS = {"User-Agent": UA, "Accept": "*/*"}
TIMEOUT = 18.0
MAX_BYTES = 12 * 1024 * 1024
IMAGE_OK = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_OK = {".mp4", ".webm", ".ogv"}


def collect_web_media(
    queries: list[str],
    dest_dir: Path,
    *,
    topic: str,
    limit: int = 16,
) -> list[MediaClip]:
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    clips: list[MediaClip] = []
    seen: set[str] = set()
    with httpx.Client(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
        for query in queries:
            if len(clips) >= limit:
                break
            q = (query or "").strip()
            if not q:
                continue
            for hit in _commons(client, q, topic) + _openverse(client, q, topic):
                url = hit.get("url") or ""
                if not url or url in seen:
                    continue
                seen.add(url)
                ext = hit.get("ext") or _ext(url)
                dest = dest_dir / f"web_{len(clips):03d}{ext}"
                if not _download(client, url, dest):
                    continue
                kind = "video" if ext in VIDEO_OK else "image"
                clips.append(
                    MediaClip(
                        path=dest,
                        duration=float(hit.get("duration") or (6.0 if kind == "video" else 4.5)),
                        source=str(hit.get("source") or "web"),
                        query=q,
                        width=int(hit.get("width") or 0),
                        height=int(hit.get("height") or 0),
                        kind=kind,
                    )
                )
                if len(clips) >= limit:
                    break
    log.info("Web media locked {} on-topic files for '{}'", len(clips), topic)
    return clips


def download_urls(urls: list[str], dest_dir: Path, *, topic: str) -> list[MediaClip]:
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    clips: list[MediaClip] = []
    with httpx.Client(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
        for url in urls:
            if not url:
                continue
            ext = _ext(url)
            dest = dest_dir / f"wiki_{len(clips):03d}{ext}"
            if not _download(client, url, dest):
                continue
            clips.append(
                MediaClip(path=dest, duration=4.8, source="wikipedia", query=topic, kind="image")
            )
    return clips


def _commons(client: httpx.Client, query: str, topic: str) -> list[dict]:
    hits: list[dict] = []
    try:
        resp = client.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": query,
                "gsrnamespace": 6,
                "gsrlimit": 16,
                "prop": "imageinfo",
                "iiprop": "url|mime|size",
                "iiurlwidth": 1280,
                "format": "json",
            },
        )
        resp.raise_for_status()
        pages = ((resp.json().get("query") or {}).get("pages") or {})
    except Exception as exc:
        log.warning("Commons search failed: {}", exc)
        return hits
    for page in pages.values():
        title = str(page.get("title") or "")
        if not hit_is_relevant(title, topic):
            continue
        info = (page.get("imageinfo") or [{}])[0]
        mime = str(info.get("mime") or "")
        url = info.get("thumburl") or info.get("url")
        if not url:
            continue
        if mime.startswith("image/"):
            ext = ".jpg" if "jpeg" in mime else (".png" if "png" in mime else ".jpg")
            hits.append({"url": url, "ext": ext, "source": "commons", "width": info.get("width") or 0, "height": info.get("height") or 0})
        elif mime.startswith("video/") or mime == "application/ogg":
            raw = info.get("url")
            if raw:
                hits.append({"url": raw, "ext": _ext(raw) or ".webm", "source": "commons", "kind": "video", "duration": 8.0})
    return hits


def _openverse(client: httpx.Client, query: str, topic: str) -> list[dict]:
    hits: list[dict] = []
    try:
        resp = client.get(
            "https://api.openverse.org/v1/images/",
            params={"q": query, "page_size": 12, "mature": False},
        )
        resp.raise_for_status()
        results = resp.json().get("results") or []
    except Exception as exc:
        log.warning("Openverse failed: {}", exc)
        return hits
    for item in results:
        title = str(item.get("title") or item.get("id") or "")
        if not hit_is_relevant(title, topic):
            continue
        url = item.get("url") or item.get("thumbnail")
        if not url:
            continue
        hits.append(
            {
                "url": url,
                "ext": _ext(url) or ".jpg",
                "source": "openverse",
                "width": item.get("width") or 0,
                "height": item.get("height") or 0,
            }
        )
    return hits


def _download(client: httpx.Client, url: str, dest: Path) -> bool:
    try:
        with client.stream("GET", url) as resp:
            if resp.status_code >= 400:
                return False
            ctype = (resp.headers.get("content-type") or "").lower()
            if "html" in ctype or "json" in ctype:
                return False
            size = 0
            with dest.open("wb") as handle:
                for chunk in resp.iter_bytes(64 * 1024):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        handle.close()
                        dest.unlink(missing_ok=True)
                        return False
                    handle.write(chunk)
        return dest.exists() and dest.stat().st_size > 4000
    except Exception as exc:
        log.warning("download failed {}: {}", url, exc)
        dest.unlink(missing_ok=True)
        return False


def _ext(url: str) -> str:
    path = url.split("?")[0].lower()
    match = re.search(r"(\.[a-z0-9]{3,4})$", path)
    if not match:
        return ".jpg"
    ext = match.group(1)
    if ext in IMAGE_OK or ext in VIDEO_OK:
        return ext
    return ".jpg"
