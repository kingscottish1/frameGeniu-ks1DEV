"""Pixabay Videos API."""

from __future__ import annotations

from pathlib import Path

import httpx

from app.providers.media.base import BaseMediaProvider, MediaClip
from app.utils.exceptions import ProviderError


class PixabayProvider(BaseMediaProvider):
    name = "pixabay"

    def __init__(self, api_keys: list[str] | None = None, timeout: float = 45.0, **kwargs):
        super().__init__(**kwargs)
        keys = [key for key in (api_keys or []) if key]
        if not keys:
            raise ProviderError("Pixabay API key is missing.", stage="media")
        self.api_key = keys[0]
        self.timeout = timeout

    def search(self, query: str, *, orientation: str = "portrait", limit: int = 8) -> list[dict]:
        params = {
            "key": self.api_key,
            "q": query,
            "video_type": "all",
            "per_page": max(3, min(int(limit), 20)),
            "safesearch": "true",
        }
        try:
            response = httpx.get("https://pixabay.com/api/videos/", params=params, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise ProviderError(f"Pixabay search failed: {exc}", stage="media") from exc
        results = []
        for video in payload.get("hits") or []:
            videos = video.get("videos") or {}
            pick = videos.get("medium") or videos.get("small") or videos.get("large")
            if not pick or not pick.get("url"):
                continue
            results.append(
                {
                    "id": video.get("id"),
                    "url": pick["url"],
                    "width": pick.get("width") or 0,
                    "height": pick.get("height") or 0,
                    "duration": float(video.get("duration") or 0),
                    "query": query,
                    "source": "pixabay",
                }
            )
        return results

    def download(self, item: dict, dest: Path) -> MediaClip:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            with httpx.stream("GET", item["url"], timeout=self.timeout, follow_redirects=True) as response:
                response.raise_for_status()
                with dest.open("wb") as handle:
                    for chunk in response.iter_bytes(1024 * 128):
                        handle.write(chunk)
        except Exception as exc:
            raise ProviderError(f"Pixabay download failed: {exc}", stage="media") from exc
        return MediaClip(
            path=dest,
            duration=float(item.get("duration") or 4.0),
            source="pixabay",
            query=str(item.get("query") or ""),
            width=int(item.get("width") or 0),
            height=int(item.get("height") or 0),
            kind="video",
        )
