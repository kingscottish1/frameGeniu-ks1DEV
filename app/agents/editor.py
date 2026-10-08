"""Editor agent — cuts, grades, mixes, burns captions, always emits an MP4."""

from __future__ import annotations

import shutil
from pathlib import Path

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.services import video as video_service
from app.utils.validators import safe_filename


class EditorAgent(BaseAgent):
    name = "editor"
    label = "Editor"
    start_progress = 74
    end_progress = 92

    def run(self, ctx: AgentContext) -> AgentResult:
        script = ctx.payload.get("script")
        audio = ctx.payload.get("audio")
        clips = ctx.payload.get("clips")
        if script is None or audio is None or not clips:
            return self.fail("Editor is missing script, voice, or footage.")
        ctx.progress(self.start_progress, self.name, "Editor is on the timeline")
        from app.config.settings import get_settings

        settings = get_settings()
        slug = safe_filename(script.title or ctx.params.topic)
        video_path = settings.files.videos / f"{ctx.task_id}_{slug}.mp4"
        track = ctx.payload.get("subtitles") if ctx.params.subtitle_enabled else None

        def tick(value: int, message: str) -> None:
            ctx.progress(value, self.name, message)

        try:
            video_service.compose_video(
                clips=clips,
                audio_path=Path(audio.path),
                script=script,
                params=ctx.params,
                subtitles=track,
                workdir=ctx.workdir,
                output=video_path,
                on_progress=tick,
            )
        except Exception as exc:
            self.log.warning("compose raised {}, hunting for a usable file", exc)
            recovered = video_service.find_task_video(ctx.task_id)
            if recovered and recovered.exists():
                if recovered.resolve() != video_path.resolve():
                    shutil.copy2(recovered, video_path)
            if not video_path.exists() or video_path.stat().st_size < 1024:
                return self.fail(str(exc))

        if not video_path.exists() or video_path.stat().st_size < 1024:
            return self.fail("Editor finished without a video file.")
        ctx.payload["video_path"] = video_path
        ctx.progress(self.end_progress, self.name, "Picture lock")
        return AgentResult(stage=self.name, data={"video_path": str(video_path)})
