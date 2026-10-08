"""B-roll: generate theme pictures first, then only keep on-topic stock."""

from __future__ import annotations

import random
import time
from pathlib import Path

from app.config.settings import get_settings
from app.models.research import ResearchBrief
from app.models.script import VideoScript
from app.models.video import VideoParams
from app.providers.media import MediaClip
from app.services.theme import detect_theme, shot_prompts, still_count
from app.services.visuals import visual_queries
from app.services.web_media import collect_web_media, download_urls
from app.utils.logger import get_logger

log = get_logger("media")


def collect_clips(
    script: VideoScript,
    params: VideoParams,
    workdir: Path,
    research: ResearchBrief | None = None,
    backgrounds: list | None = None,
) -> list[MediaClip]:
    settings = get_settings()
    provider_name = params.media_provider or settings.media_provider
    workdir = Path(workdir)
    media_dir = workdir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    theme = detect_theme(params.topic, params.template)
    # Lock the grade so crime looks like crime.
    if not params.color_grade or params.color_grade == "cinematic":
        params.color_grade = theme.grade

    extra = []
    if research:
        extra.extend(research.people)
    extra.extend(script.search_terms or [])
    queries = visual_queries(params.topic, extra=extra, template=theme.id)
    if not queries:
        queries = [params.topic]

    clips: list[MediaClip] = []
    if backgrounds:
        clips.extend(backgrounds)

    want = still_count(float(getattr(params, "duration", 0) or 30))
    # Paint remaining unique stills if the backgrounds agent came up short.
    if len(clips) < want:
        try:
            from app.services.imagine import generate_image

            ai_dir = media_dir / "ai"
            ai_dir.mkdir(parents=True, exist_ok=True)
            w, h = params.size()
            gw, gh = (min(w, 768), min(h, 1344)) if w < h else (min(w, 1280), min(h, 768))
            dur = float(getattr(params, "duration", 0) or 30)
            stamp = time.time_ns()
            prompts = shot_prompts(params.topic, params.template, limit=want, duration=dur, salt=str(stamp))
            for index, prompt in enumerate(prompts):
                if len(clips) >= want:
                    break
                dest = ai_dir / f"ai_{index:02d}.jpg"
                try:
                    seed = (int(stamp) ^ (index * 104729) ^ (hash(params.topic) & 0xFFFFFFFF)) % 999_983
                    generate_image(prompt, width=gw, height=gh, dest=dest, seed=seed)
                    if dest.exists() and dest.stat().st_size > 4000:
                        clips.append(MediaClip(path=dest, duration=4.8, source="imagine", query=params.topic, kind="image"))
                except Exception as exc:
                    log.warning("AI still failed: {}", exc)
        except Exception as exc:
            log.warning("imagine unavailable: {}", exc)

    # Wiki photos only as a last gap-fill — they repeat across films of the same subject.
    if research and research.image_urls and len(clips) < 4:
        try:
            clips.extend(download_urls(research.image_urls[:6], media_dir / "wiki", topic=params.topic))
        except Exception as exc:
            log.warning("wiki images failed: {}", exc)

    # 3. Real stock B-roll even when media.provider = "local".
    # Coverr is keyless. Pexels/Pixabay only if a real key is set (not ********).
    timeout = float(settings.media.get("download_timeout") or 45)
    orientation = "portrait" if params.aspect_ratio.value in {"9:16", "4:5"} else "landscape"
    if params.aspect_ratio.value == "1:1":
        orientation = "square"
    providers = _stock_providers(settings, timeout, prefer=provider_name)
    seen_urls: set[str] = set()
    stock_want = min(6, max(2, want // 5 + 2))
    stock_got = 0
    for provider in providers:
        if stock_got >= stock_want:
            break
        name = getattr(provider, "name", "stock")
        for index, query in enumerate(queries[:5]):
            if stock_got >= stock_want:
                break
            try:
                hits = provider.search(query, orientation=orientation, limit=4)
            except Exception as exc:
                log.warning("Search failed for '{}' on {}: {}", query, name, exc)
                continue
            random.shuffle(hits)
            for hit in hits:
                url = str(hit.get("url") or "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                dest = media_dir / f"stock_{name}_{index:02d}_{stock_got:02d}.mp4"
                try:
                    clip = provider.download(hit, dest)
                    if dest.exists() and dest.stat().st_size > 8_000:
                        clips.append(clip)
                        stock_got += 1
                        break
                except Exception as exc:
                    log.warning("Download failed ({}): {}", name, exc)

    # 4. Commons last, titles must mention the topic — never openverse pets
    if getattr(params, "research_enabled", True) and len(clips) < 4:
        try:
            clips.extend(collect_web_media(queries[:3], media_dir / "web", topic=params.topic, limit=4))
        except Exception as exc:
            log.warning("Web media failed: {}", exc)

    unique: list[MediaClip] = []
    seen: set[str] = set()
    for clip in clips:
        key = str(Path(clip.path).resolve())
        if key in seen or not Path(clip.path).exists():
            continue
        seen.add(key)
        unique.append(clip)

    if not unique:
        raise RuntimeError("No media clips could be prepared.")
    log.info("Locked {} themed clips ({}) for '{}'", len(unique), theme.id, params.topic)
    return unique


def _real_keys(values) -> list[str]:
    return [str(k).strip() for k in (values or []) if str(k).strip() and "****" not in str(k)]


def _stock_providers(settings, timeout: float, prefer: str = "") -> list:
    from app.providers.media.coverr import CoverrProvider
    from app.providers.media.pexels import PexelsProvider
    from app.providers.media.pixabay import PixabayProvider

    out = []
    try:
        out.append(CoverrProvider(timeout=timeout))
    except Exception as exc:
        log.warning("Coverr unavailable: {}", exc)
    pexels = _real_keys(settings.media.get("pexels_api_keys"))
    if pexels:
        try:
            out.append(PexelsProvider(api_keys=pexels, timeout=timeout))
        except Exception as exc:
            log.warning("Pexels unavailable: {}", exc)
    pixabay = _real_keys(settings.media.get("pixabay_api_keys"))
    if pixabay:
        try:
            out.append(PixabayProvider(api_keys=pixabay, timeout=timeout))
        except Exception as exc:
            log.warning("Pixabay unavailable: {}", exc)
    name = (prefer or "").lower().strip()
    if name in {"pexels", "pixabay", "coverr"}:
        out.sort(key=lambda provider: 0 if getattr(provider, "name", "") == name else 1)
    return out
