"""Coverr stock footage — public search, no API key."""

from __future__ import annotations

from pathlib import Path

import httpx

from app.providers.media.base import BaseMediaProvider, MediaClip
from app.utils.exceptions import ProviderError

UA = "FrameGenius/1.11 (local video studio by kingscottishDEV N.A.S)"
CDN = "https://cdn.coverr.co/videos"


def coverr_mp4_url(base_filename: str, quality: str = "720p") -> str:
    """Public Coverr CDN path — no API key. Prefer GET (HEAD may return HTML)."""
    base = str(base_filename or "").strip().strip("/")
    if not base:
        return ""
    q = quality if quality in {"360p", "720p", "1080p"} else "720p"
    return f"{CDN}/{base}/{q}.mp4"


class CoverrProvider(BaseMediaProvider):
    name = "coverr"

    def __init__(self, api_key: str = "", timeout: float = 45.0, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key or ""
        self.timeout = timeout

    def search(self, query: str, *, orientation: str = "portrait", limit: int = 8) -> list[dict]:
        headers = {"User-Agent": UA, "Accept": "application/json"}
        params = {"query": query or "cinematic", "page_size": 20}
        try:
            response = httpx.get(
                "https://coverr.co/api/videos",
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise ProviderError(f"Coverr search failed: {exc}", stage="media") from exc
        hits = list(payload.get("hits") or [])
        if orientation == "portrait":
            vertical = [h for h in hits if h.get("is_vertical")]
            hits = vertical + [h for h in hits if h not in vertical]
        results = []
        for video in hits:
            if video.get("is_premium"):
                continue
            url = coverr_mp4_url(str(video.get("base_filename") or ""))
            if not url:
                continue
            base = str(video.get("base_filename") or "").strip()
            results.append(
                {
                    "id": video.get("id") or video.get("video_id") or base,
                    "url": url,
                    "width": int(video.get("max_width") or 1280),
                    "height": int(video.get("max_height") or 720),
                    "duration": float(video.get("duration") or 8),
                    "query": query,
                    "source": "coverr",
                    "title": str(video.get("title") or ""),
                }
            )
            if len(results) >= max(1, int(limit)):
                break
        return results

    def download(self, item: dict, dest: Path) -> MediaClip:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        headers = {"User-Agent": UA, "Accept": "video/mp4,*/*"}
        try:
            with httpx.stream(
                "GET", item["url"], headers=headers, timeout=self.timeout, follow_redirects=True
            ) as response:
                response.raise_for_status()
                with dest.open("wb") as handle:
                    for chunk in response.iter_bytes(1024 * 128):
                        handle.write(chunk)
        except Exception as exc:
            raise ProviderError(f"Coverr download failed: {exc}", stage="media") from exc
        if dest.stat().st_size < 8000:
            dest.unlink(missing_ok=True)
            raise ProviderError("Coverr returned an empty file.", stage="media")
        return MediaClip(
            path=dest,
            duration=float(item.get("duration") or 4.0),
            source="coverr",
            query=str(item.get("query") or ""),
            width=int(item.get("width") or 0),
            height=int(item.get("height") or 0),
            kind="video",
        )
