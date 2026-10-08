"""Script generation — Ollama / cloud LLM, or the studio writer if they are offline."""

from __future__ import annotations

import json
import re
from typing import Any

from app.config.defaults import DEFAULT_SYSTEM_PROMPT
from app.config.settings import get_settings
from app.models.research import ResearchBrief
from app.models.script import Scene, VideoScript
from app.services import llm as llm_service
from app.services.topiclock import (
    allowed_names,
    keep_note,
    lock_narration,
    on_subject,
    same_story,
    strip_off_topic,
    unused_notes,
)
from app.utils.logger import get_logger

log = get_logger("script")

_JSON_RE = re.compile(r"\{[\s\S]*\}")
_THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.I)

# Spoken words at -15% Edge ≈ 140 wpm ≈ 2.4 words/sec.
# 30s≈72, 5m≈720, 30m≈4320. Notes (the 10–11k chew pile) are separate.
_WORDS_PER_SEC = 2.75


def _drop_off_topic_scenes(script: VideoScript, topic: str, research=None) -> VideoScript:
    """Drop detours. Do not shred an on-subject Ollama script."""
    allowed = allowed_names(topic, research, script.narration[:2500] if script else "")
    locked = lock_narration(script.narration, topic, allowed)
    if locked and locked != script.narration:
        log.info("Locked narration to the subject ({} → {} words)", len(script.narration.split()), len(locked.split()))
        script.raw_text = locked
        script.apply_timings()
    return script

def _word_target(duration: float) -> int:
    seconds = float(duration or 30)
    words = int(round(seconds * _WORDS_PER_SEC))
    # Slight overshoot so Edge at -15% still fills 1m / 5m / 10m.
    if seconds >= 50:
        words = int(round(words * 1.08))
    return max(40, words)


def _notes_target(duration: float) -> int:
    """Chew pile for the writer. 1m→6k, 5m→10k, 10m→12k. Not a thin skim."""
    seconds = float(duration or 30)
    if seconds <= 45:
        return 3000
    if seconds <= 90:
        return 6000
    if seconds <= 360:
        return 10000
    return 12000


def _scene_seconds(narration: str) -> float:
    words = max(4, len((narration or "").split()))
    return float(min(90.0, max(2.6, words / _WORDS_PER_SEC)))


def generate_script(
    topic: str,
    *,
    language: str = "en",
    template: str = "motivational",
    duration: float = 30.0,
    custom_script: str | None = None,
    provider: str | None = None,
    ollama_model: str | None = None,
    research: ResearchBrief | None = None,
) -> VideoScript:
    if custom_script and custom_script.strip():
        return _from_plain_text(topic, custom_script, language=language, template=template)

    # Films are written by Ollama from research notes — never the demo/studio faker.
    polished = _try_llm_script(
        topic,
        language=language,
        template=template,
        duration=duration,
        provider=provider,
        ollama_model=ollama_model,
        research=research,
    )
    if polished and polished.scenes and _script_is_speakable(polished):
        return _locked_script(polished, topic, research)
    if research and research.spoken_pool():
        # Real scraped facts only. Do not invent a motivational template.
        fallback = _script_from_research(topic, research, language=language, template=template, duration=duration)
        if fallback.scenes and _script_is_speakable(fallback):
            log.warning("Ollama missed — using on-subject research facts, not invented copy")
            return _locked_script(fallback, topic, research)
    if research and (research.summary or research.facts):
        blob = research.summary or " ".join(research.facts[:12])
        return _from_plain_text(topic, blob, language=language, template=template)
    if (provider or "").lower() in {"demo", "studio"}:
        return _studio_script(topic, language=language, template=template, duration=duration)
    raise RuntimeError("Ollama did not write a script and there is no research. Start Ollama and retry.")


def _locked_script(script: VideoScript, topic: str, research=None) -> VideoScript:
    """Topic-lock must never kill a finished voiceover."""
    try:
        return _drop_off_topic_scenes(script, topic, research)
    except Exception as exc:
        log.warning("topic lock skipped: {}", exc)
        return script


def _try_llm_script(
    topic: str,
    *,
    language: str,
    template: str,
    duration: float,
    provider: str | None,
    ollama_model: str | None,
    research: ResearchBrief | None,
) -> VideoScript | None:
    settings = get_settings()
    name = (provider or settings.llm_provider or "auto").lower()
    if name in {"demo", "local", "none", "offline", "studio", "auto", "local-first", ""}:
        name = "ollama"
    facts = _research_notes(research, topic, duration=duration)
    log.info("Ollama chew pile: {} words for '{}'", len(facts.split()), topic)
    words_target = _word_target(duration)
    minutes = max(1, int(round(duration / 60.0))) if duration >= 50 else 0
    length_hint = f"{int(duration)} seconds" if duration < 90 else f"{minutes} minutes ({int(duration)} seconds)"
    prompt = (
        f"Write a spoken voiceover about: {topic}\n"
        f"Language: {language}. Tone: {template}.\n"
        f"LENGTH: at least {words_target} words so it lasts {length_hint} when read aloud.\n"
        "Keep writing until you hit that word count. Do not stop after a short intro.\n"
        "This will be read aloud on camera by a British presenter. Write ONLY the words they speak.\n"
        "Sound like a person telling the story, not an essay and not a chatbot.\n"
        "Rules:\n"
        "- Short spoken sentences. Contractions. British English.\n"
        "- Never write: delve, tapestry, landscape of, in this video, let's explore, it's important to note, furthermore, moreover, in conclusion, as we can see.\n"
        "- Short clear sentences. No lists of random words.\n"
        "- No URLs, no code, no brackets, no hashtags, no wiki markup, no citations like [1].\n"
        "- STAY ON THIS SUBJECT for the whole script. Do not switch to a different person or story.\n"
        "- Do not invent names, dates, places, or events that are not in the notes.\n"
        "- If a fact is not in the notes, skip it. Do not guess.\n"
        "- Do not introduce a footballer, club, or any other biography that is not the subject.\n"
        "- If the notes run thin, go deeper on the same events: timeline, motives, aftermath, why it still matters.\n"
        "- If you finish the notes, STOP. Do not invent a different case, person, country, or random story.\n"
        "- Do not dump the notes. Rewrite them as a story someone would actually say.\n"
        "- End with the exact line: Sub and follow.\n"
        "- Output plain text paragraphs. No JSON. No markdown.\n"
    )
    if facts:
        prompt += "Notes from the web (use these, do not read them verbatim):\n" + facts + "\n"
    system = (
        "You are a documentary voiceover writer. You write spoken narration "
        "ONLY from the research notes. If it is not in the notes, you do not say it. "
        "Never invent people, dates, or cases. Never output code, JSON, or markup. "
        "Stay on the given subject from the first sentence to the last."
    )
    try:
        llm = llm_service.get_llm(name)
        if ollama_model and getattr(llm, "pick_model", None):
            try:
                llm.model = llm.pick_model(ollama_model)
            except Exception:
                llm.model = ollama_model
        elif ollama_model:
            llm.model = ollama_model
        if hasattr(llm, "timeout"):
            llm.timeout = max(float(getattr(llm, "timeout", 300) or 300), min(1800, 120 + float(duration) * 1.2))
        if hasattr(llm, "num_ctx") and duration >= 50:
            llm.num_ctx = max(int(getattr(llm, "num_ctx", 0) or 0), 32768)
        raw = llm.generate(
            prompt,
            system=system,
            temperature=0.45 if duration >= 90 else 0.65,
            max_tokens=min(12000, max(900, words_target * 2)),
        )
        raw = _THINK_RE.sub("", raw or "").strip()
        if not raw or not _is_speakable(raw[:400]):
            return None
        raw = strip_off_topic(raw, topic) or raw
        raw = _grow_voiceover(
            llm,
            topic=topic,
            text=raw,
            words_target=words_target,
            system=system,
            facts=facts,
        )
        raw = strip_off_topic(raw, topic) or raw
        raw = _scrub_speech(raw) or raw
        script = _from_plain_text(topic, raw, language=language, template=template)
        script.scenes = [s for s in script.scenes if s.narration.strip() and not _is_junk(s.narration)]
        if not script.scenes:
            return None
        script.raw_text = " ".join(s.narration for s in script.scenes)
        script.apply_timings()
        log.info(
            "AI script: {} scenes, {} words, {:.0f}s spoken (target {:.0f}s)",
            len(script.scenes),
            len(script.narration.split()),
            script.estimated_duration(),
            duration,
        )
        return script
    except Exception as exc:
        log.warning("LLM script failed: {}", exc)
    return None


def _deepen_same_subject(llm, *, topic: str, text: str, need: int, system: str) -> str:
    """More spoken words without a new biography. Same people, same story."""
    prompt = (
        f"Keep narrating {topic}. Write about {need} more spoken words.\n"
        "Stay on the same subject and the same people already named.\n"
        "Go deeper: timeline, motives, aftermath, why it still matters.\n"
        "Do not invent a new person. Do not talk about a footballer or a club unless that is the subject.\n"
        "No title. No JSON. Plain spoken paragraphs. Do not repeat the last lines.\n"
        "Already written (do not repeat):\n" + (text or "")[-1600:]
    )
    try:
        extra = llm.generate(prompt, system=system, temperature=0.55, max_tokens=min(4000, max(400, need * 3)))
    except Exception as exc:
        log.warning("deepen failed: {}", exc)
        return ""
    extra = _THINK_RE.sub("", extra or "").strip()
    extra = extra.replace("Sub and follow.", "").strip()
    return extra


def _fill_from_notes(text: str, facts: str, topic: str, words_target: int) -> str:
    """Pad with leftover research sentences — never invented people."""
    leftover = unused_notes(facts, text) if facts else ""
    if not leftover:
        return text
    blob = text.rstrip()
    allow = allowed_names(topic, spoken=blob[:2500])
    seen = {_norm(blob)}
    for line in leftover.splitlines():
        if len(blob.split()) >= int(words_target * 0.96):
            break
        sent = line.lstrip("- ").strip()
        if len(sent.split()) < 8:
            continue
        if sent[-1] not in ".!?":
            sent += "."
        if not same_story(sent, topic, allow) or not on_subject(sent, topic):
            continue
        key = _norm(sent)
        if not key or key in seen:
            continue
        seen.add(key)
        blob = (blob + " " + sent).strip()
    return blob


def _grow_voiceover(llm, *, topic: str, text: str, words_target: int, system: str, facts: str = "") -> str:
    """Keep going from leftover notes. Stop instead of inventing a new story."""
    blob = text
    for _step in range(8):
        have = len(blob.split())
        if have >= int(words_target * 0.96):
            return blob
        leftover = unused_notes(facts, blob) if facts else ""
        if not leftover:
            log.info("script short ({}/{} words) but notes are spent — not inventing", have, words_target)
            break
        need = words_target - have
        if need < 20:
            return blob
        log.info("script short ({}/{} words) — rewriting leftover notes", have, words_target)
        extra_prompt = (
            f"Continue the voiceover about {topic}. Write about {need} more spoken words.\n"
            "Use ONLY the unused notes below. Do not add a new person, place, or story.\n"
            "Do not repeat anything already spoken. Cover the next unused facts in order.\n"
            "No title. No JSON. Plain spoken paragraphs.\n"
            "Unused notes:\n" + leftover[:8000] + "\n"
            "Already written (do not repeat):\n" + blob[-1600:]
        )
        extra = ""
        try:
            extra = llm.generate(
                extra_prompt,
                system=system,
                temperature=0.4,
                max_tokens=min(5000, max(400, need * 3)),
            )
        except Exception as exc:
            log.warning("script continue failed: {}", exc)
        extra = _THINK_RE.sub("", extra or "").strip()
        extra = re.sub(r"(?i)^(sure|okay|ok|here(?:'s| is) more|continuing)[:.\s]+", "", extra).strip()
        extra = lock_narration(extra, topic, allowed_names(topic, spoken=blob[:2000])) if extra else ""
        if extra and len(extra.split()) >= 20 and not on_subject(extra, topic) and not on_subject(blob[-800:] + " " + extra, topic):
            log.info("script continue left the subject — skipping this chunk")
            extra = ""
        if extra and len(extra.split()) >= 20:
            extra = extra.replace("Sub and follow.", "").strip()
            blob = (blob.rstrip() + " " + extra).strip()
        else:
            log.info("script continue drifted — not dumping raw notes")
            break
        if "sub and follow" not in blob.lower():
            blob = blob.rstrip() + " Sub and follow."
    return blob



def extend_narration(
    script: VideoScript,
    *,
    topic: str,
    need_words: int,
    provider: str | None = None,
    ollama_model: str | None = None,
    research: ResearchBrief | None = None,
    duration: float = 0.0,
) -> str:
    """More spoken words, rewritten from leftover on-subject notes. Never dump wiki."""
    if need_words < 20:
        return ""
    orig_n = len(script.narration.split())
    dur = float(duration or 0) or max(30.0, orig_n / max(_WORDS_PER_SEC, 0.5) + need_words / _WORDS_PER_SEC)
    facts = _research_notes(research, topic, duration=dur)
    leftover = unused_notes(facts, script.narration) if facts else ""
    if not leftover:
        return ""
    settings = get_settings()
    name = (provider or settings.llm_provider or "auto").lower()
    if name in {"demo", "local", "none", "offline", "studio", "auto", "local-first", ""}:
        name = "ollama"
    try:
        llm = llm_service.get_llm(name)
        if ollama_model and getattr(llm, "pick_model", None):
            try:
                llm.model = llm.pick_model(ollama_model)
            except Exception:
                llm.model = ollama_model
        elif ollama_model:
            llm.model = ollama_model
        extra = llm.generate(
            (
                f"Continue the voiceover about {topic}. Write about {need_words} more spoken words.\n"
                "Use ONLY the unused notes. Stay on this subject. Do not invent a new person or case.\n"
                "Plain spoken paragraphs. No JSON. No title.\n"
                "Unused notes:\n" + leftover[:6000] + "\n"
                "Already spoken (do not repeat):\n" + script.narration[-1200:]
            ),
            system="You write spoken narration about one subject only.",
            temperature=0.4,
            max_tokens=min(4000, max(400, need_words * 3)),
        )
    except Exception as exc:
        log.warning("extend narration failed: {}", exc)
        return ""
    extra = _THINK_RE.sub("", extra or "").strip()
    extra = re.sub(r"(?i)sub and follow\\.?", "", extra).strip()
    extra = lock_narration(extra, topic, allowed_names(topic, research, script.narration[:2000]))
    if extra and not on_subject(extra, topic):
        return ""
    return extra if len(extra.split()) >= 15 else ""



def _research_notes(research: ResearchBrief | None, topic: str, duration: float = 30.0) -> str:
    """Feed Ollama on-subject articles — 10k+ words on a 10m film. No scrape salad."""
    if not research:
        return ""
    from app.services.topiclock import keep_page

    target = min(12000, _notes_target(duration))
    chunks: list[str] = []
    if research.summary and keep_note(research.summary, topic) and not _is_junk(research.summary):
        chunks.append(research.summary.strip())
    for item in research.facts or []:
        if item and keep_note(item, topic) and not _is_junk(item) and (_is_speakable(item) or len(item.split()) >= 8):
            chunks.append(item.strip())
    for block in research.extracts or []:
        if not keep_page(block, topic) and not on_subject(block[:1800], topic):
            continue
        text = _scrub_speech(block) or " ".join((block or "").split())
        step = 700
        for i in range(0, len(text), step):
            piece = text[i : i + 900].strip()
            if len(piece.split()) < 16 or _is_junk(piece[:80]):
                continue
            chunks.append(piece)
    seen: set[str] = set()
    lines: list[str] = []
    words = 0
    for item in chunks:
        key = _norm(item[:180])
        if not key or key in seen:
            continue
        seen.add(key)
        lines.append("- " + item[:900])
        words += len(item.split())
        if words >= target:
            break
    log.info("Ollama notes packed: {} words (target {})", words, target)
    return "\n".join(lines)


def _script_from_research(
    topic: str,
    research: ResearchBrief,
    *,
    language: str,
    template: str,
    duration: float,
) -> VideoScript:
    """Build a unique spoken script from research. Never pad by repeating lines."""
    unique = _unique_sentences(research, topic)
    if not unique and research.summary:
        unique = [research.summary.split(".")[0].strip() + "."]
    intro = unique[0] if unique else topic
    if len(intro.split()) > 18:
        intro = " ".join(intro.split()[:18]).rstrip(",;:") + "."
    outro = _outro_line(topic, template)
    words_needed = _word_target(duration)
    picked = [intro]
    word_count = len(intro.split())
    seen = {_norm(intro)}
    for sent in unique[1:]:
        key = _norm(sent)
        if key in seen:
            continue
        seen.add(key)
        picked.append(sent)
        word_count += len(sent.split())
        if word_count >= words_needed:
            break
    if _norm(outro) not in seen:
        picked.append(outro)
    # If we still need more unique words, write fresh angles from leftover extract
    # fragments — never recycle a line we already spoke.
    if word_count < words_needed:
        extras = _expand_unique(topic, template, research, seen, words_needed - word_count)
        picked.extend(extras)

    visuals = research.visual_queries() or [topic, f"{topic} archive", f"{topic} portrait"]
    scenes = _scenes_from_lines(picked, visuals)
    title_src = research.summary.split(".")[0] if research.summary else topic
    title = re.sub(r"\s*\([^)]*\)", "", title_src or topic).strip()[:80]
    script = VideoScript(
        title=title or topic.title(),
        description=research.summary or f"A researched {template} film about {topic}.",
        hook=intro[:180],
        language=language,
        template=template,
        scenes=scenes,
        raw_text=" ".join(scene.narration for scene in scenes),
    )
    script.apply_timings()
    log.info(
        "Research script: {} unique scenes, {} words, {:.0f}s spoken (target {:.0f}s)",
        len(scenes),
        len(script.narration.split()),
        script.estimated_duration(),
        duration,
    )
    return script


def _unique_sentences(research: ResearchBrief, topic: str) -> list[str]:
    cite = re.compile(r"\[[0-9]{1,3}\]")
    seen: set[str] = set()
    out: list[str] = []
    for block in research.spoken_pool():
        clean = cite.sub("", block or "")
        for sent in re.split(r"(?<=[.!?])\s+", clean):
            sent = " ".join(sent.split()).strip()
            if not _is_speakable(sent):
                continue
            if sent[-1] not in ".!?":
                sent += "."
            # drop wiki disambiguation junk
            if sent.lower().startswith("this article is about") or "may refer to" in sent.lower():
                continue
            if not keep_note(sent, topic):
                continue
            key = _norm(sent)
            if key in seen or len(key) < 20:
                continue
            seen.add(key)
            out.append(sent)
    return out


def _expand_unique(topic: str, template: str, research: ResearchBrief, seen: set[str], need_words: int) -> list[str]:
    """More research sentences only. Never pad with stock 'file / press conference' lines."""
    leftover = _unique_sentences(research, topic)
    picked: list[str] = []
    words = 0
    for sent in leftover:
        key = _norm(sent)
        if key in seen:
            continue
        seen.add(key)
        picked.append(sent)
        words += len(sent.split())
        if words >= need_words:
            break
    return picked


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", (text or "").lower())


def _is_junk(text: str) -> bool:
    sent = " ".join((text or "").split())
    if not sent:
        return True
    if any(ch in sent for ch in "#{}<>[]\\|`"):
        return True
    if re.search(r"[\[\]{}<>#\\|`]{2,}|['\"]\s*[\[\]#]|#as\b", sent):
        return True
    if re.search(r"https?://|www\.|function\s*\(|ISBN|PMID|\.js\b|var\s+\w+\s*=", sent, re.I):
        return True
    punct = len(re.findall(r"[^A-Za-z0-9\s'.]", sent))
    if punct / max(len(sent), 1) > 0.16:
        return True
    return False


def _is_speakable(text: str) -> bool:
    """Reject scrape junk, code, wiki markup, and random symbol salad."""
    sent = " ".join((text or "").split())
    if len(sent) < 24:
        return False
    if _is_junk(sent):
        return False
    low = sent.lower()
    banned = (
        "this article is about",
        "may refer to",
        "coordinates:",
        "retrieved",
        "external links",
        "jump to",
        "edit section",
        "javascript",
    )
    if any(b in low for b in banned):
        return False
    letters = len(re.findall(r"[A-Za-z]", sent))
    if letters < 20:
        return False
    if letters / max(len(sent), 1) < 0.62:
        return False
    return True


def _scrub_speech(text: str) -> str:
    """Strip scrape salad so the voice never reads '][]['# or wiki markup."""
    blob = _THINK_RE.sub("", text or "")
    blob = re.sub(r"\[[0-9]{1,3}\]", "", blob)
    blob = re.sub(r"\[\[.*?\]\]", " ", blob)
    blob = re.sub(r"\{\{.*?\}\}", " ", blob)
    blob = re.sub(r"['\"][\[\]#]+[^\s]*", " ", blob)
    blob = re.sub(r"[\[\]{}<>#\\|`]{2,}", " ", blob)
    blob = re.sub(r"(?i)\b(javascript|function\s*\(|var\s+\w+\s*=)\b.*", " ", blob)
    kept: list[str] = []
    for sent in re.split(r"(?<=[.!?])\s+", blob):
        sent = " ".join(sent.split()).strip()
        if not sent or _is_junk(sent) or len(sent) < 8:
            continue
        if sent[-1] not in ".!?":
            sent += "."
        kept.append(sent)
    return " ".join(kept)


def _script_is_speakable(script: VideoScript) -> bool:
    blob = script.narration or ""
    if blob and _is_junk(blob[:400]):
        return False
    if not script.scenes:
        return False
    bad = sum(1 for s in script.scenes if _is_junk(s.narration))
    return bad <= max(1, len(script.scenes) // 5)


def _scenes_from_lines(lines: list[str], visuals: list[str]) -> list[Scene]:
    scenes: list[Scene] = []
    bucket: list[str] = []
    bucket_words = 0
    for sent in lines:
        bucket.append(sent)
        bucket_words += len(sent.split())
        if bucket_words >= 16:
            narration = " ".join(bucket)
            search = visuals[len(scenes) % len(visuals)]
            scenes.append(
                Scene(
                    narration=narration,
                    search=search,
                    visual=search,
                    duration=_scene_seconds(narration),
                )
            )
            bucket, bucket_words = [], 0
    if bucket:
        narration = " ".join(bucket)
        search = visuals[len(scenes) % max(1, len(visuals))]
        scenes.append(
            Scene(
                narration=narration,
                search=search,
                visual=search,
                duration=_scene_seconds(narration),
            )
        )
    return scenes


def _intro_line(topic: str, template: str, research: ResearchBrief) -> str:
    from app.services.hook import punch_hook

    return punch_hook(topic, research)


def _outro_line(topic: str, template: str) -> str:
    return "Sub and follow."


def _from_plain_text(topic: str, text: str, *, language: str, template: str) -> VideoScript:
    blob = _scrub_speech(text) or _THINK_RE.sub("", text or "").strip()
    sentences: list[str] = []
    for part in re.split(r"\n+", blob):
        part = part.strip()
        if not part or _is_junk(part):
            continue
        bits = [s.strip() for s in re.split(r"(?<=[.!?])\s+", part) if s.strip()]
        sentences.extend(bits or [part])
    sentences = [s for s in sentences if not _is_junk(s)]
    if sentences and "sub and follow" not in " ".join(sentences).lower():
        sentences.append("Sub and follow.")
    visuals = [_keywords(topic), f"{topic} portrait", f"{topic} archive"]
    if not sentences:
        scenes = []
    elif len(sentences) <= 8:
        scenes = []
        for index, chunk in enumerate(sentences):
            scenes.append(
                Scene(
                    narration=chunk,
                    search=_keywords(topic if index == 0 else chunk),
                    visual=chunk[:80],
                    duration=_scene_seconds(chunk),
                )
            )
    else:
        scenes = _scenes_from_lines(sentences, visuals)
    script = VideoScript(
        title=topic.title(),
        description=f"Custom script about {topic}",
        hook=(sentences[0][:140] if sentences else topic),
        language=language,
        template=template,
        scenes=scenes,
        raw_text=" ".join(scene.narration for scene in scenes) if scenes else blob,
    )
    script.apply_timings()
    return script


def _parse_llm_json(raw: str, *, topic: str, language: str, template: str) -> VideoScript:
    raw = _THINK_RE.sub("", raw or "")
    raw = raw.replace("```json", "").replace("```", "")
    match = _JSON_RE.search(raw)
    if not match:
        return _from_plain_text(topic, raw, language=language, template=template)
    try:
        data: dict[str, Any] = json.loads(match.group(0))
    except json.JSONDecodeError:
        cleaned = match.group(0)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return _from_plain_text(topic, raw, language=language, template=template)
    scenes = []
    for item in data.get("scenes") or []:
        if isinstance(item, str):
            scenes.append(Scene(narration=item, search=_keywords(item)))
            continue
        narration = str(item.get("narration") or item.get("text") or "").strip()
        if not narration:
            continue
        scenes.append(
            Scene(
                narration=narration,
                search=str(item.get("search") or item.get("keywords") or _keywords(narration)),
                visual=str(item.get("visual") or ""),
                duration=float(item.get("duration") or _scene_seconds(narration)),
            )
        )
    return VideoScript(
        title=str(data.get("title") or topic.title()),
        description=str(data.get("description") or ""),
        hook=str(data.get("hook") or (scenes[0].narration if scenes else topic)),
        language=str(data.get("language") or language),
        template=template,
        scenes=scenes,
        raw_text=" ".join(scene.narration for scene in scenes),
    )


def _keywords(text: str) -> str:
    words = re.findall(r"[A-Za-z]{4,}", text.lower())
    stop = {
        "this", "that", "with", "from", "your", "about", "have", "will", "just",
        "them", "they", "what", "when", "make", "more", "into", "than", "then",
        "every", "their", "there", "would", "could", "should", "because",
    }
    keep = [word for word in words if word not in stop]
    return " ".join(keep[:5]) or "cinematic b-roll"


def _is_unique_script(script: VideoScript) -> bool:
    norms = [_norm(scene.narration) for scene in script.scenes if scene.narration]
    return bool(norms) and len(norms) == len(set(norms))


def _studio_script(topic: str, *, language: str, template: str, duration: float) -> VideoScript:
    builder = TEMPLATES.get(template) or TEMPLATES["motivational"]
    scenes = builder(topic, duration)
    script = VideoScript(
        title=topic.title(),
        description=f"A {template} FrameGenius short about {topic}.",
        hook=scenes[0].narration if scenes else topic,
        language=language,
        template=template,
        scenes=scenes,
        raw_text=" ".join(scene.narration for scene in scenes),
    )
    script.apply_timings()
    return script


def _demo_script(topic: str, *, language: str, template: str, duration: float) -> VideoScript:
    return _studio_script(topic, language=language, template=template, duration=duration)


def _pack(lines: list[tuple[str, str]], duration: float) -> list[Scene]:
    """One unique scene per line. Never loop the same sentence to pad runtime."""
    if not lines:
        return []
    scenes: list[Scene] = []
    seen: set[str] = set()
    for narration, search in lines:
        key = _norm(narration)
        if key in seen:
            continue
        seen.add(key)
        scenes.append(
            Scene(
                narration=narration,
                search=search,
                visual=search,
                duration=_scene_seconds(narration),
            )
        )
    return scenes


def _motivational(topic: str, duration: float) -> list[Scene]:
    return _pack(
        [
            (f"Nobody is coming to save you. {topic} starts with the next decision you make.", "sunrise mountain runner silhouette"),
            ("Most people wait for motivation. Builders show up when it is quiet.", "empty gym early morning lights"),
            (f"Treat {topic} like a craft. One honest rep. Then another.", "close up hands working craft wood"),
            ("The gap between who you are and who you want to be is just a calendar.", "flipping calendar pages cinematic"),
            ("Stop narrating the struggle. Film the comeback.", "city night walking confident"),
            ("Start smaller than your ego wants. Stay longer than your mood wants.", "ocean waves long exposure dawn"),
            (f"That is how {topic} stops being a wish and becomes a record.", "finish line stadium lights"),
        ],
        duration,
    )


def _educational(topic: str, duration: float) -> list[Scene]:
    return _pack(
        [
            (f"Here is {topic} explained so you will actually remember it.", "library warm lamp notebook"),
            ("First, strip the jargon. Name the moving parts in plain language.", "whiteboard sketch diagram"),
            ("Second, find the one rule that makes the rest click.", "macro gears turning closeup"),
            ("Third, test it on a tiny real example before you scale.", "scientist pouring liquid glass"),
            ("If you cannot teach it in one breath, you do not own it yet.", "teacher pointing at chalkboard"),
            (f"Save this. Replay it. Then go use {topic} today.", "student closing laptop smile"),
        ],
        duration,
    )


def _entertainment(topic: str, duration: float) -> list[Scene]:
    return _pack(
        [
            (f"Okay but why is {topic} suddenly everywhere?", "neon city night crowd"),
            ("Plot twist: the internet did not invent this. It just turned the volume up.", "vintage tv static closeup"),
            ("One clip. One comment. Entire timelines lose their minds.", "phone screen scrolling social"),
            ("Meanwhile the people who made it are just... living their lives.", "backstage concert lights"),
            (f"So yes. {topic} is chaotic. That is the entertainment.", "fireworks over skyline"),
            ("Stay till the end. You will never unsee it.", "cinema audience dark glow"),
        ],
        duration,
    )


def _product(topic: str, duration: float) -> list[Scene]:
    return _pack(
        [
            (f"If {topic} feels harder than it should, the tool is the problem.", "messy desk frustrated night"),
            ("You do not need more tabs. You need a cleaner path.", "minimal workspace sunlight"),
            ("FrameGenius writes the script, speaks it, finds the footage, and cuts the film.", "timeline editing software glow"),
            ("Portrait or landscape. Captions that slap. Music underneath.", "vertical phone video creator"),
            (f"Ship the video. Iterate tomorrow. That is how {topic} grows.", "upload button cinematic macro"),
        ],
        duration,
    )


def _story(topic: str, duration: float) -> list[Scene]:
    return _pack(
        [
            (f"I used to think {topic} was a talent problem.", "rain window night reflection"),
            ("It was not talent. It was a system I refused to build.", "old notebook handwritten notes"),
            ("The day everything changed was boring. No montage. Just a decision.", "empty street dawn walking"),
            ("I cut the noise. I kept the reps. I let the work be ugly.", "workshop sparks metal"),
            (f"If you are in the middle of {topic} right now — stay. The plot twist is you.", "sunrise over quiet city"),
        ],
        duration,
    )


def _news(topic: str, duration: float) -> list[Scene]:
    return _pack(
        [
            (f"Here is what actually matters about {topic} today.", "news studio bokeh city"),
            ("Skip the panic headline. Look at the underlying shift.", "stock market charts screens"),
            ("The people closest to the problem already changed their behavior.", "commuters train station rush"),
            ("That is the signal. Everything else is commentary.", "satellite earth night lights"),
            (f"Watch {topic} over the next week. The pattern will be obvious.", "time-lapse skyline dusk"),
        ],
        duration,
    )


def _crime(topic: str, duration: float) -> list[Scene]:
    return _pack(
        [
            (f"They told you {topic} was simple. The file says otherwise.", "crime scene tape night rain"),
            ("Start with the last 24 hours. Who moved. Who went quiet. Who cashed out.", "cctv hallway grainy footage"),
            ("The official story is a press conference. The real story is a paper trail.", "court documents stacked closeup"),
            ("Follow the money, the phone, the camera that was never supposed to be on.", "city night surveillance cameras"),
            ("A name keeps coming back. Not in the headlines. In the footnotes.", "old newspaper microfilm closeup"),
            ("Everyone had a reason to look away. That is how this stayed buried.", "empty parking garage fluorescent"),
            (f"This is the {topic} deep dive. The sources are in the description.", "interrogation room single lamp"),
            (f"A second name sits in the margin of the {topic} file. Nobody read it out loud.", "pencil circling a name on paper"),
            (f"If {topic} still feels simple, you stopped one page too early.", "closing a thick case folder"),
        ],
        duration,
    )


def _true_crime(topic: str, duration: float) -> list[Scene]:
    return _pack(
        [
            (f"Three things do not add up about {topic}.", "red and blue lights wet asphalt"),
            ("First: the timeline. The call came in late. The body was already cold.", "analog clock midnight closeup"),
            ("Second: the witness who changed their story after talking to a lawyer.", "court hallway empty benches"),
            ("Third: the money that moved the same night, then vanished.", "bank vault stacks cash night"),
            ("Detectives had a suspect. The file had a hole. Someone filled it.", "detective desk case files lamp"),
            (f"If you think you know {topic}, you have only heard the press version.", "old tv news broadcast static"),
        ],
        duration,
    )


TEMPLATES = {
    "motivational": _motivational,
    "educational": _educational,
    "entertainment": _entertainment,
    "product": _product,
    "story": _story,
    "news": _news,
    "crime": _crime,
    "crime-deep-dive": _crime,
    "crime_deep_dives": _crime,
    "true-crime": _true_crime,
    "true_crime": _true_crime,
}
