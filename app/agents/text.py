"""Text agent — locks the on-screen copy (hook, titles, caption colour)."""

from __future__ import annotations

import json

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.services.theme import detect_theme


class TextAgent(BaseAgent):
    name = "text"
    label = "Text"
    start_progress = 25
    end_progress = 31

    def run(self, ctx: AgentContext) -> AgentResult:
        script = ctx.payload.get("script")
        if script is None:
            return self.fail("Writer did not hand off a script.")
        ctx.progress(self.start_progress, self.name, "Text is locking titles and captions")
        theme = detect_theme(ctx.params.topic, ctx.params.template)
        hook = (script.hook or script.title or ctx.params.topic).strip()[:140]
        titles = [script.title, ctx.params.topic.title(), hook]
        seen: set[str] = set()
        unique_titles: list[str] = []
        for item in titles:
            key = (item or "").strip()
            if not key or key.lower() in seen:
                continue
            seen.add(key.lower())
            unique_titles.append(key)
        payload = {
            "hook": hook,
            "titles": unique_titles[:3],
            "theme": theme.id,
            "font_color": theme.font_color,
            "highlight": theme.highlight,
            "grade": theme.grade,
        }
        path = ctx.workdir / "text.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        ctx.payload["text"] = payload
        ctx.payload["theme"] = theme
        if not ctx.params.color_grade or ctx.params.color_grade == "cinematic":
            ctx.params.color_grade = theme.grade
        ctx.progress(self.end_progress, self.name, f"Copy locked · {theme.id}")
        return AgentResult(stage=self.name, message=hook, data=payload)
