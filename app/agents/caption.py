"""Caption agent — builds SRT + styled ASS."""

from __future__ import annotations

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.services import subtitle as subtitle_service


class CaptionAgent(BaseAgent):
    name = "caption"
    label = "Caption"
    start_progress = 60
    end_progress = 70
    optional = True

    def run(self, ctx: AgentContext) -> AgentResult:
        script = ctx.payload.get("script")
        audio = ctx.payload.get("audio")
        if script is None or audio is None:
            return self.fail("Need writer + voice before captions.")
        ctx.progress(self.start_progress, self.name, "Caption is timing words")
        from app.services.theme import detect_theme

        theme = ctx.payload.get("theme") or detect_theme(ctx.params.topic, ctx.params.template)
        try:
            track = subtitle_service.build_subtitles(
                script,
                words=audio.words,
                audio_path=audio.path,
                duration=audio.duration,
                workdir=ctx.workdir,
                theme=theme,
                seed=f"{ctx.task_id}|{ctx.params.topic}",
            )
        except Exception as exc:
            # Captions must never kill a render — editor still exports the MP4.
            self.log.warning("caption build failed ({}), retrying without theme", exc)
            try:
                track = subtitle_service.build_subtitles(
                    script,
                    words=audio.words,
                    audio_path=audio.path,
                    duration=audio.duration,
                    workdir=ctx.workdir,
                )
            except Exception as exc2:
                self.log.warning("caption fallback failed: {}", exc2)
                ctx.progress(self.end_progress, self.name, "Captions skipped")
                return AgentResult(stage=self.name, message="captions skipped", data={"cues": 0})
        ctx.payload["subtitles"] = track
        ctx.progress(self.end_progress, self.name, f"{len(track.cues)} cues")
        return AgentResult(stage=self.name, data={"cues": len(track.cues), "srt": track.srt_path})
