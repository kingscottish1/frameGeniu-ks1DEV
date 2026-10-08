"""Pexels Videos API."""

from __future__ import annotations

from pathlib import Path

import httpx

from app.providers.media.base import BaseMediaProvider, MediaClip
from app.utils.exceptions import ProviderError


class PexelsProvider(BaseMediaProvider):
    name = "pexels"

    def __init__(self, api_keys: list[str] | None = None, timeout: float = 45.0, **kwargs):
        super().__init__(**kwargs)
        keys = [key for key in (api_keys or []) if key]
        if not keys:
            raise ProviderError("Pexels API key is missing.", stage="media")
        self.api_keys = keys
        self.timeout = timeout
        self._index = 0

    def _headers(self) -> dict[str, str]:
        key = self.api_keys[self._index % len(self.api_keys)]
        self._index += 1
        return {"Authorization": key}

    def search(self, query: str, *, orientation: str = "portrait", limit: int = 8) -> list[dict]:
        params = {
            "query": query,
            "per_page": max(1, min(int(limit), 15)),
            "orientation": orientation if orientation in {"portrait", "landscape", "square"} else "portrait",
        }
        try:
            response = httpx.get(
                "https://api.pexels.com/videos/search",
                params=params,
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise ProviderError(f"Pexels search failed: {exc}", stage="media") from exc
        results = []
        for video in payload.get("videos") or []:
            files = sorted(
                video.get("video_files") or [],
                key=lambda item: int(item.get("width") or 0),
                reverse=True,
            )
            pick = None
            for item in files:
                width = int(item.get("width") or 0)
                if 720 <= width <= 1920 and item.get("link"):
                    pick = item
                    break
            pick = pick or (files[0] if files else None)
            if not pick or not pick.get("link"):
                continue
            results.append(
                {
                    "id": video.get("id"),
                    "url": pick["link"],
                    "width": pick.get("width") or 0,
                    "height": pick.get("height") or 0,
                    "duration": float(video.get("duration") or 0),
                    "query": query,
                    "source": "pexels",
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
            raise ProviderError(f"Pexels download failed: {exc}", stage="media") from exc
        return MediaClip(
            path=dest,
            duration=float(item.get("duration") or 4.0),
            source="pexels",
            query=str(item.get("query") or ""),
            width=int(item.get("width") or 0),
            height=int(item.get("height") or 0),
            kind="video",
        )
