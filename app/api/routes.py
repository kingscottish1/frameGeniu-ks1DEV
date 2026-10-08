"""API route mounting."""

from __future__ import annotations

from fastapi import APIRouter, FastAPI

from app.controllers import agent, auth, config, dashboard, factory, health, publish, reskin, task, upload, video


def mount_routes(app: FastAPI) -> None:
    api = APIRouter(prefix="/api/v1")
    api.include_router(health.router)
    api.include_router(auth.router)
    api.include_router(agent.router)
    api.include_router(video.router)
    api.include_router(task.router)
    api.include_router(config.router)
    api.include_router(upload.router)
    api.include_router(reskin.router)
    api.include_router(publish.router)
    api.include_router(factory.router)
    api.include_router(dashboard.router)
    app.include_router(api)
    app.include_router(health.router, prefix="/api")
