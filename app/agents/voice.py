"""Voice agent — speaks the script. Keeps going until the picked length is filled."""

from __future__ import annotations

from pathlib import Path

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.services import voice as voice_service


class VoiceAgent(BaseAgent):
    name = "voice"
    label = "Voice"
    start_progress = 32
    end_progress = 40

    def run(self, ctx: AgentContext) -> AgentResult:
        script = ctx.payload.get("script")
        if script is None:
            return self.fail("Writer did not hand off a script.")
        ctx.progress(self.start_progress, self.name, "Voice is recording")
        dest = ctx.workdir / "voice.mp3"
        audio = voice_service.synthesize(
            script.narration,
            dest,
            voice=ctx.params.voice,
            provider=ctx.params.tts_provider,
        )
        target = float(getattr(ctx.params, "duration", 0) or 0)
        # 5 min picks were landing at ~3:30. Keep writing + speaking until we fill it.
        tries = 0
        while target >= 90 and audio.duration + 4 < target * 0.94 and tries < 8:
            tries += 1
            need_sec = max(20.0, target - audio.duration)
            need_words = max(40, int(need_sec * 2.5))
            ctx.progress(
                min(39, self.start_progress + tries),
                self.name,
                f"Voice short ({audio.duration:.0f}s / {target:.0f}s) — writing more",
            )
            try:
                from app.services.script import extend_narration

                extra = extend_narration(
                    script,
                    topic=ctx.params.topic,
                    need_words=need_words,
                    provider=ctx.params.llm_provider,
                    ollama_model=ctx.params.ollama_model,
                    research=ctx.payload.get("research"),
                    duration=target,
                )
            except Exception as exc:
                self.log.warning("voice extend failed: {}", exc)
                break
            if not extra:
                break
            part = ctx.workdir / f"voice_more_{tries}.mp3"
            more = voice_service.synthesize(
                extra,
                part,
                voice=ctx.params.voice,
                provider=ctx.params.tts_provider,
            )
            joined = ctx.workdir / f"voice_joined_{tries}.mp3"
            audio = voice_service.join_audio(audio, more, joined)
            script.raw_text = (script.narration + " " + extra).strip()
            if "sub and follow" not in script.raw_text.lower():
                script.raw_text = script.raw_text.rstrip() + " Sub and follow."
            ctx.payload["script"] = script
            # copy joined onto voice.mp3 so later stages find it
            try:
                import shutil

                if Path(audio.path).resolve() != dest.resolve():
                    shutil.copy2(audio.path, dest)
                audio.path = str(dest)
            except Exception:
                pass
        ctx.payload["audio"] = audio
        ctx.progress(self.end_progress, self.name, f"Voice bed {audio.duration:.1f}s")
        return AgentResult(stage=self.name, data={"duration": audio.duration, "path": audio.path})
