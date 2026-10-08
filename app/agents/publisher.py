"""Publisher agent — thumbnail, post kit, result envelope."""

from __future__ import annotations

from pathlib import Path

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.services import postkit, video as video_service


class PublisherAgent(BaseAgent):
    name = "publisher"
    label = "Publisher"
    start_progress = 93
    end_progress = 100

    def run(self, ctx: AgentContext) -> AgentResult:
        video_path = ctx.payload.get("video_path")
        script = ctx.payload.get("script")
        audio = ctx.payload.get("audio")
        track = ctx.payload.get("subtitles")
        research = ctx.payload.get("research")
        if not video_path:
            return self.fail("No picture lock to publish.")
        ctx.progress(self.start_progress, self.name, "Building the post kit")
        from app.config.settings import get_settings

        settings = get_settings()
        thumb = settings.files.thumbnails / f"{ctx.task_id}.jpg"
        try:
            video_service.make_thumbnail(Path(video_path), thumb)
        except Exception as exc:
            self.log.warning("Thumbnail failed: {}", exc)
            thumb = Path("")
        try:
            from app.services.cards import hook_words, paint_thumbnail
            from app.services.channel import brand_label
            from app.services.imagine import generate_image

            hook = hook_words(getattr(script, "hook", "") or ctx.params.topic, 6)
            ai_base = ctx.workdir / "thumb_ai.jpg"
            try:
                generate_image(
                    f"{ctx.params.topic}, cinematic social thumbnail still, dramatic light",
                    width=min(ctx.params.size()[0], 768),
                    height=min(ctx.params.size()[1], 1344),
                    dest=ai_base,
                    seed=int(ctx.task_id[:8], 16) % 999983,
                    allow_text=False,
                )
                if ai_base.exists() and ai_base.stat().st_size > 4000:
                    thumb_base = ai_base
                else:
                    thumb_base = thumb if thumb and Path(thumb).exists() else None
            except Exception:
                thumb_base = thumb if thumb and Path(thumb).exists() else None
            paint_thumbnail(
                thumb,
                headline=hook,
                kicker=brand_label(),
                footer=getattr(script, "title", "") or ctx.params.topic,
                base=thumb_base,
                size=ctx.params.size(),
            )
        except Exception as exc:
            self.log.warning("poster thumb failed: {}", exc)
        duration = video_service.probe_duration(video_path) or (audio.duration if audio else 0)
        shorts = {}
        if getattr(ctx.params, "cut_shorts", True) and duration >= 70 and script:
            try:
                from app.services.shorts import cut_shorts

                shorts_dir = settings.files.videos / "shorts" / ctx.task_id
                shorts = cut_shorts(
                    video=Path(video_path),
                    script=script,
                    duration=duration,
                    dest_dir=shorts_dir,
                    task_id=ctx.task_id,
                    ffmpeg=settings.ffmpeg,
                )
                if shorts.get("zip"):
                    packed = settings.files.videos / f"{ctx.task_id}_shorts.zip"
                    try:
                        import shutil as _sh

                        _sh.copy2(shorts["zip"], packed)
                        shorts["zip"] = str(packed)
                    except OSError:
                        pass
            except Exception as exc:
                self.log.warning("shorts skipped: {}", exc)
        companion = None
        if getattr(ctx.params, "dual_export", True):
            try:
                wide = settings.files.videos / f"wide-{ctx.task_id}.mp4"
                companion = video_service.export_companion(
                    Path(video_path), wide, ctx.params.size(), settings.ffmpeg
                )
            except Exception as exc:
                self.log.warning("dual export skipped: {}", exc)
        size = Path(video_path).stat().st_size if Path(video_path).exists() else 0
        kit = {}
        try:
            kit = postkit.build_postkit(
                topic=ctx.params.topic,
                script=script,
                research=research,
                track=track,
                duration=duration,
                workdir=ctx.workdir,
                video_name=Path(video_path).name,
                thumb_name=thumb.name if thumb else "",
            )
            kit_zip = settings.files.videos / f"{ctx.task_id}_postkit.zip"
            postkit.zip_kit(ctx.workdir, kit_zip)
            ctx.payload["kit_zip"] = kit_zip
        except Exception as exc:
            self.log.warning("post kit failed: {}", exc)
            kit_zip = Path("")
        result = {
            "video_path": str(video_path),
            "thumbnail_path": str(thumb) if thumb else "",
            "script_path": str(ctx.payload.get("script_path") or ""),
            "subtitle_path": getattr(track, "srt_path", "") if track else "",
            "kit_path": str(kit_zip) if kit_zip else "",
            "postkit": kit,
            "duration": duration,
            "bytes": size,
            "filename": Path(video_path).name,
            "title": kit.get("title") or getattr(script, "title", ctx.params.topic),
            "download_url": f"/api/v1/videos/{ctx.task_id}/download",
            "stream_url": f"/api/v1/videos/{ctx.task_id}/stream",
            "kit_url": f"/api/v1/videos/{ctx.task_id}/kit",
            "sources": kit.get("sources") or [],
            "hashtags": kit.get("hashtags") or [],
            "tags": kit.get("hashtags") or [],
            "captions_url": f"/api/v1/videos/{ctx.task_id}/captions",
            "tags_url": f"/api/v1/videos/{ctx.task_id}/tags",
            "shorts_url": f"/api/v1/videos/{ctx.task_id}/shorts" if shorts.get("zip") else "",
            "shorts_count": shorts.get("count") or 0,
            "titles": kit.get("titles") or [],
            "hook": getattr(script, "hook", "") or ctx.params.topic,
            "companion_path": str(companion) if companion else "",
            "companion_url": f"/api/v1/videos/{ctx.task_id}/wide" if companion else "",
            "agents": [
                "research",
                "writer",
                "text",
                "voice",
                "backgrounds",
                "media",
                "caption",
                "editor",
                "publisher",
            ],
        }
        try:
            from app.services.janitor import sweep
            from app.services.ship import ship_today

            srt = Path(getattr(track, "srt_path", "") or "")
            post_md = ctx.workdir / "POST.md"
            shipped = ship_today(
                output_dir=settings.files.output_dir,
                topic=ctx.params.topic,
                series_name=str(getattr(ctx.params, "series_name", "") or ""),
                series_part=getattr(ctx.params, "series_part", None),
                video=Path(video_path),
                companion=companion,
                thumb=thumb if thumb else None,
                titles=kit.get("titles") or [],
                tags=kit.get("hashtags") or [],
                captions=srt if srt.exists() else None,
                post_md=post_md if post_md.exists() else None,
            )
            result["today_folder"] = shipped.get("folder") or ""
            result["today_prefix"] = shipped.get("prefix") or ""
        except Exception as exc:
            self.log.warning("TODAY ship skipped: {}", exc)
        try:
            from app.services.janitor import sweep

            sweep()
        except Exception as exc:
            self.log.warning("janitor skipped: {}", exc)
        ctx.payload["result"] = result
        ctx.progress(self.end_progress, self.name, "Ready to post")
        return AgentResult(stage=self.name, message="Ready to post", data=result)
