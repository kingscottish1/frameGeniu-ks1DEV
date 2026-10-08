"""HTTP hardening: headers, CORS lockdown, rate limits, request budget."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

from app.security.rate_limit import limiter
from app.utils.env import env, env_bool

PUBLIC_PREFIXES = (
    "/api/v1/health",
    "/api/health",
    "/api/v1/auth/login",
    "/api/v1/auth/status",
    "/brand/",
    "/dashboard/",
    "/login",
    "/favicon",
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and request.url.path.endswith("/auth/login"):
            ip = request.client.host if request.client else "unknown"
            if not limiter.allow(f"login:{ip}", 6, 60):
                return JSONResponse({"detail": "Too many login attempts"}, status_code=429)
        if request.url.path.startswith("/api/"):
            ip = request.client.host if request.client else "unknown"
            if not limiter.allow(f"api:{ip}", 180, 60):
                return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)

        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > 12 * 1024 * 1024:
            return JSONResponse({"detail": "Request too large"}, status_code=413)

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["X-FrameGenius"] = "kingscottishDEV-N.A.S"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else response.headers.get("Cache-Control", "no-cache")
        csp = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data: blob:; "
            "media-src 'self' blob:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        response.headers["Content-Security-Policy"] = csp
        if env_bool("FRAMEGENIUS_HSTS", False):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if "server" in response.headers:
            del response.headers["server"]
        return response


def allowed_origins() -> list[str]:
    raw = env("FRAMEGENIUS_CORS_ORIGINS", "") or ""
    items = [part.strip() for part in raw.split(",") if part.strip()]
    if items:
        return items
    # Same-origin dashboard — no wildcard.
    return [
        "http://127.0.0.1:8080",
        "http://localhost:8080",
        "http://127.0.0.1:8501",
        "http://localhost:8501",
    ]


def install_hardening(app: FastAPI) -> None:
    origins = allowed_origins()
    extra = env("FRAMEGENIUS_PUBLIC_ORIGIN")
    if extra and extra not in origins:
        origins.append(extra)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-CSRF-Token"],
        allow_credentials=True,
    )
    app.add_middleware(SecurityHeadersMiddleware)

    @app.middleware("http")
    async def access_log(request: Request, call_next):
        path = request.url.path
        # never log query strings — they may contain tokens
        response = await call_next(request)
        logger.debug("{} {} → {}", request.method, path, response.status_code)
        return response
