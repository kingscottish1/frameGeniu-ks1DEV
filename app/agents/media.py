"""Media scout agent — finds B-roll or local stills."""

from __future__ import annotations

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.services import stock_media


class MediaScoutAgent(BaseAgent):
    name = "media"
    label = "Media scout"
    start_progress = 51
    end_progress = 58

    def run(self, ctx: AgentContext) -> AgentResult:
        script = ctx.payload.get("script")
        if script is None:
            return self.fail("Writer did not hand off a script.")
        ctx.progress(self.start_progress, self.name, "Generating pictures for this topic")
        clips = stock_media.collect_clips(
            script,
            ctx.params,
            ctx.workdir,
            research=ctx.payload.get("research"),
            backgrounds=ctx.payload.get("backgrounds"),
        )
        if not clips:
            return self.fail("No footage could be prepared.")
        ctx.payload["clips"] = clips
        ctx.progress(self.end_progress, self.name, f"Scout locked {len(clips)} clips")
        return AgentResult(stage=self.name, data={"clips": len(clips)})
