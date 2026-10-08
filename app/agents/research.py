"""Research agent — scrapes the public web for the topic."""

from __future__ import annotations

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.models.research import ResearchBrief
from app.services import research as research_service


class ResearchAgent(BaseAgent):
    name = "research"
    label = "Research"
    start_progress = 2
    end_progress = 12

    def run(self, ctx: AgentContext) -> AgentResult:
        if not getattr(ctx.params, "research_enabled", True):
            brief = ResearchBrief(topic=ctx.params.topic)
            ctx.payload["research"] = brief
            return AgentResult(stage=self.name, message="Research skipped", data={"sources": 0})
        ctx.progress(self.start_progress, self.name, "Research is scraping the web")
        dur = float(ctx.params.duration or 30)
        if dur <= 45:
            pages, note_words = 8, 3000
        elif dur <= 90:
            pages, note_words = 12, 6000
        elif dur <= 360:
            pages, note_words = 18, 10000
        else:
            pages, note_words = 24, 12000
        try:
            brief = research_service.research_topic(
                ctx.params.topic, max_pages=pages, min_words=note_words
            )
        except Exception as exc:
            self.log.warning("Research failed: {}", exc)
            brief = ResearchBrief(topic=ctx.params.topic)
        path = ctx.workdir / "research.json"
        path.write_text(brief.model_dump_json(indent=2), encoding="utf-8")
        ctx.payload["research"] = brief
        ctx.payload["research_path"] = path
        ctx.progress(
            self.end_progress,
            self.name,
            f"{len(brief.sources)} sources · {len(brief.facts)} facts · {sum(len((e or '').split()) for e in brief.extracts)} note words",
        )
        return AgentResult(
            stage=self.name,
            message=brief.summary[:80] if brief.summary else ctx.params.topic,
            data={"sources": len(brief.sources), "facts": len(brief.facts)},
        )
