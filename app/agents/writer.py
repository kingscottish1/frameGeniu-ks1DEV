"""Writer agent — turns a topic into a spoken script."""

from __future__ import annotations

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.services import script as script_service


class WriterAgent(BaseAgent):
    name = "writer"
    label = "Writer"
    start_progress = 13
    end_progress = 24

    def run(self, ctx: AgentContext) -> AgentResult:
        ctx.progress(self.start_progress, self.name, "Writer is drafting narration")
        params = ctx.params
        provider = (params.llm_provider or "auto").lower()
        if provider in {"auto", "studio", "demo", "local", "none", ""}:
            provider = "ollama"
        script = script_service.generate_script(
            params.topic,
            language=params.language,
            template=params.template,
            duration=params.duration,
            custom_script=params.script_text,
            provider=provider,
            ollama_model=params.ollama_model,
            research=ctx.payload.get("research"),
        )
        try:
            from app.services.hook import shape_script

            script = shape_script(
                script,
                params.topic,
                hook_lock=bool(getattr(params, "hook_lock", True)),
                series_name=str(getattr(params, "series_name", "") or ""),
                series_part=getattr(params, "series_part", None),
                series_total=getattr(params, "series_total", None),
                research=ctx.payload.get("research"),
            )
        except Exception as exc:
            self.log.warning("story shape skipped: {}", exc)
        from app.config.settings import get_settings

        script_path = ctx.workdir / "script.json"
        script_path.write_text(script.model_dump_json(indent=2), encoding="utf-8")
        archive = get_settings().files.scripts / f"{ctx.task_id}.json"
        archive.write_text(script.model_dump_json(indent=2), encoding="utf-8")
        ctx.payload["script"] = script
        ctx.payload["script_path"] = archive
        ctx.progress(self.end_progress, self.name, f"Writer locked {len(script.scenes)} scenes")
        return AgentResult(
            stage=self.name,
            message=script.title,
            data={"title": script.title, "scenes": len(script.scenes)},
        )
