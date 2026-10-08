"""Ready-to-post package: titles, description, hashtags, chapters, sources."""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

from app.models.research import ResearchBrief
from app.models.script import VideoScript
from app.models.subtitle import SubtitleTrack
from app.utils.logger import get_logger

log = get_logger("postkit")


def build_postkit(
    *,
    topic: str,
    script: VideoScript,
    research: ResearchBrief | None,
    track: SubtitleTrack | None,
    duration: float,
    workdir: Path,
    video_name: str,
    thumb_name: str = "",
) -> dict:
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    titles = _titles(topic, script)
    hashtags = _hashtags(topic, script, research)
    chapters = _chapters(script)
    description = _description(topic, script, research, chapters, hashtags)
    kit = {
        "title": titles[0],
        "titles": titles,
        "description": description,
        "hashtags": hashtags,
        "chapters": chapters,
        "sources": [src.model_dump() for src in (research.sources if research else [])],
        "duration": duration,
        "video": video_name,
        "thumbnail": thumb_name,
        "captions": "subtitles.srt" if track and track.srt_path else "",
    }
    (workdir / "postkit.json").write_text(json.dumps(kit, ensure_ascii=False, indent=2), encoding="utf-8")
    (workdir / "POST.md").write_text(_markdown(kit), encoding="utf-8")
    (workdir / "description.txt").write_text(description, encoding="utf-8")
    (workdir / "hashtags.txt").write_text(" ".join(hashtags), encoding="utf-8")
    (workdir / "tags.txt").write_text("\n".join(hashtags) + "\n", encoding="utf-8")
    if track and track.srt_path:
        kit["captions"] = "subtitles.srt"
    return kit


def zip_kit(workdir: Path, dest: Path) -> Path:
    workdir = Path(workdir)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    names = [
        "POST.md",
        "postkit.json",
        "description.txt",
        "hashtags.txt",
        "tags.txt",
        "subtitles.srt",
        "subtitles.ass",
        "script.json",
        "research.json",
    ]
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in names:
            path = workdir / name
            if path.exists():
                zf.write(path, name)
    return dest


def _titles(topic: str, script: VideoScript) -> list[str]:
    raw = (script.title or topic).strip()
    base = re.sub(r"\s*\([^)]*\)", "", raw).split(",")[0].strip()[:80] or topic.strip()
    hook = (script.hook or topic).strip()
    titles = [
        base[:90],
        f"{topic.strip()[:70]} — the full story",
        (hook[:80] if hook and hook.lower() != base.lower() else f"What nobody told you about {topic.strip()[:50]}"),
    ]
    seen: set[str] = set()
    out: list[str] = []
    for item in titles:
        key = item.lower()
        if key in seen or not item:
            continue
        seen.add(key)
        out.append(item)
    return out


_THEME_TAGS = {
    "crime": ["#TrueCrime", "#Documentary", "#CrimeStory", "#DeepDive"],
    "true-crime": ["#TrueCrime", "#Documentary", "#CrimeStory", "#DeepDive"],
    "gym": ["#Gym", "#Fitness", "#Training", "#Discipline"],
    "news": ["#News", "#Explained", "#Today"],
    "motivational": ["#Mindset", "#Motivation", "#Discipline"],
    "educational": ["#Explained", "#Learn", "#Documentary"],
    "entertainment": ["#Storytime", "#Viral"],
    "product": ["#Review", "#Product"],
    "story": ["#Story", "#Documentary"],
}


def _hashtags(topic: str, script: VideoScript, research: ResearchBrief | None) -> list[str]:
    raw = [topic, getattr(script, "template", "") or "", "documentary", "explained", "deepdive"]
    if research:
        raw.extend(research.people[:4])
        raw.extend((research.keywords or [])[:4] if hasattr(research, "keywords") else [])
    tags: list[str] = []
    seen: set[str] = set()

    def add(tag: str) -> None:
        tag = (tag or "").strip()
        if not tag:
            return
        if not tag.startswith("#"):
            slug = re.sub(r"[^A-Za-z0-9]+", "", tag)
            if len(slug) < 3:
                return
            tag = "#" + slug[:28]
        low = tag.lower()
        if low in seen:
            return
        seen.add(low)
        tags.append(tag)

    theme = (getattr(script, "template", "") or "").lower()
    blob = f"{topic} {theme}".lower()
    if any(w in blob for w in ("crime", "kingpin", "mafia", "cartel", "murder", "kinahan")):
        theme = "crime"
    for item in _THEME_TAGS.get(theme, ["#Documentary", "#Explained"]):
        add(item)
    for item in raw:
        add(item)
    add("#FrameGenius")
    add("#CrownAI")
    return tags[:16]


def _chapters(script: VideoScript) -> list[dict]:
    chapters: list[dict] = []
    if not script.scenes:
        return chapters
    step = max(1, len(script.scenes) // 8)
    for index, scene in enumerate(script.scenes):
        if index == 0 or index % step == 0 or index == len(script.scenes) - 1:
            label = (scene.visual or scene.search or scene.narration)[:48]
            chapters.append({"at": round(scene.start, 1), "label": label})
    # de-dupe close timestamps
    cleaned: list[dict] = []
    last = -30.0
    for item in chapters:
        if item["at"] - last < 12:
            continue
        cleaned.append(item)
        last = item["at"]
    return cleaned[:14]


def _description(topic, script, research, chapters, hashtags) -> str:
    lines = [
        script.hook or topic,
        "",
        script.description or f"A FrameGenius film about {topic}.",
        "",
    ]
    if research and research.summary:
        lines += [research.summary[:400], ""]
    if chapters:
        lines.append("Chapters")
        for item in chapters:
            lines.append(f"{_ts(item['at'])} {item['label']}")
        lines.append("")
    if research and research.sources:
        lines.append("Sources")
        for src in research.sources[:10]:
            if src.url:
                lines.append(f"- {src.title}: {src.url}")
        lines.append("")
    lines.append(" ".join(hashtags))
    lines.append("")
    lines.append("Made with FrameGenius — kingscottishDEV N.A.S")
    return "\n".join(lines)


def _markdown(kit: dict) -> str:
    titles = "\n".join(f"- {t}" for t in kit.get("titles") or [])
    chapters = "\n".join(f"- {_ts(c['at'])} {c['label']}" for c in kit.get("chapters") or [])
    sources = "\n".join(f"- [{s.get('title')}]({s.get('url')})" for s in kit.get("sources") or [] if s.get("url"))
    return (
        f"# {kit.get('title')}\n\n"
        f"## Titles\n{titles}\n\n"
        f"## Description\n\n{kit.get('description')}\n\n"
        f"## Hashtags\n\n{' '.join(kit.get('hashtags') or [])}\n\n"
        f"## Chapters\n{chapters}\n\n"
        f"## Sources\n{sources}\n\n"
        f"## Files\n- video: {kit.get('video')}\n- captions: {kit.get('captions')}\n- thumb: {kit.get('thumbnail')}\n"
    )


def _ts(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"
