"""FastAPI application factory."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import __author__, __version__
from app.api.routes import mount_routes
from app.security.auth import COOKIE_NAME, resolve_user
from app.security.bootstrap import bootstrap
from app.security.hardening import install_hardening
from app.utils.env import env_bool
from app.utils.file_manager import ROOT


def create_app() -> FastAPI:
    bootstrap(ROOT)
    try:
        from app.services.janitor import sweep

        sweep()
    except Exception:
        pass
    expose_docs = env_bool("FRAMEGENIUS_EXPOSE_DOCS", False)
    app = FastAPI(
        title="FrameGenius API",
        description="AI video generation studio by kingscottishDEV N.A.S",
        version=__version__,
        contact={"name": __author__},
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/v1/openapi.json" if expose_docs else None,
    )
    install_hardening(app)
    mount_routes(app)

    dash = ROOT / "dashboard"
    brand = ROOT / "resource" / "icons"
    if brand.exists():
        app.mount("/brand", StaticFiles(directory=str(brand)), name="brand")
    if dash.exists():
        assets = dash / "assets"
        if assets.exists():
            app.mount("/dashboard/assets", StaticFiles(directory=str(assets)), name="dash-assets")

    @app.get("/favicon.png")
    def favicon():
        icon = brand / "favicon.png"
        if icon.exists():
            return FileResponse(icon)
        return RedirectResponse("/brand/logo.png")

    @app.get("/")
    def root():
        index = dash / "index.html"
        if index.exists():
            return FileResponse(index, media_type="text/html")
        return RedirectResponse("/api/v1/health")

    @app.get("/login")
    def login_page():
        page = dash / "index.html"
        if page.exists():
            return FileResponse(page)
        return RedirectResponse("/")

    @app.get("/docs")
    def docs(request: Request, fg_session: str | None = None):
        from fastapi import Cookie

        user = resolve_user(request, request.cookies.get(COOKIE_NAME))
        if not expose_docs and not user:
            return RedirectResponse("/")
        return get_swagger_ui_html(openapi_url="/openapi.json", title="FrameGenius API")

    @app.get("/openapi.json")
    def openapi_spec(request: Request):
        user = resolve_user(request, request.cookies.get(COOKIE_NAME))
        if not expose_docs and not user:
            return RedirectResponse("/")
        return app.openapi()

    return app
