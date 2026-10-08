"""Backgrounds agent — fresh pictures for THIS film, enough to cover the length."""

from __future__ import annotations

import hashlib
import time

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.providers.media.base import MediaClip
from app.services.imagine import generate_image
from app.services.theme import detect_theme, film_stills, shot_prompts, still_count


class BackgroundsAgent(BaseAgent):
    name = "backgrounds"
    label = "Backgrounds"
    start_progress = 41
    end_progress = 50
    optional = True

    def run(self, ctx: AgentContext) -> AgentResult:
        script = ctx.payload.get("script")
        if script is None:
            return self.fail("Need a script before backgrounds.")
        duration = float(getattr(ctx.params, "duration", 0) or 30)
        want = still_count(duration)
        ctx.progress(self.start_progress, self.name, f"Backgrounds is painting {want} fresh stills")
        theme = ctx.payload.get("theme") or detect_theme(ctx.params.topic, ctx.params.template)
        folder = ctx.workdir / "backgrounds"
        folder.mkdir(parents=True, exist_ok=True)
        width, height = ctx.params.size()
        gw, gh = (min(width, 768), min(height, 1344)) if width < height else (min(width, 1280), min(height, 768))
        try:
            prompts = film_stills(
                ctx.params.topic,
                script=script,
                research=ctx.payload.get("research"),
                limit=want,
                duration=duration,
                salt=ctx.task_id,
            )
        except Exception:
            prompts = shot_prompts(ctx.params.topic, ctx.params.template, limit=want, duration=duration, salt=ctx.task_id)
        if not prompts:
            prompts = [f"{ctx.params.topic}, photoreal cinematic still, no text, unique frame 1"]
        clips: list[MediaClip] = []
        stamp = int(time.time())
        for index, prompt in enumerate(prompts[:want]):
            seed = _seed(ctx.task_id, ctx.params.topic, index, stamp)
            dest = folder / f"bg_{index + 1:02d}.jpg"
            try:
                generate_image(prompt, width=gw, height=gh, dest=dest, seed=seed)
            except Exception as exc:
                self.log.warning("background {} failed: {}", index, exc)
                continue
            if dest.exists() and dest.stat().st_size > 4000:
                clips.append(
                    MediaClip(
                        path=dest,
                        duration=5.0,
                        source="backgrounds",
                        query=ctx.params.topic,
                        kind="image",
                    )
                )
            if index + 1 < want:
                pct = self.start_progress + int((index + 1) / want * (self.end_progress - self.start_progress - 1))
                ctx.progress(min(49, pct), self.name, f"Painted {len(clips)}/{want} stills")
        if not clips:
            return self.fail("Could not generate topic backgrounds.")
        ctx.payload["backgrounds"] = clips
        ctx.progress(self.end_progress, self.name, f"{len(clips)} new stills · {theme.id if hasattr(theme, 'id') else theme}")
        return AgentResult(stage=self.name, data={"stills": len(clips)})


def _seed(task_id: str, topic: str, index: int, stamp: int) -> int:
    raw = hashlib.sha1(f"{task_id}|{topic}|{index}|{stamp}".encode("utf-8")).hexdigest()
    return int(raw[:8], 16) % 999_983
