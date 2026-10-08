#!/usr/bin/env python3
"""FrameGenius FastAPI entrypoint — kingscottishDEV N.A.S."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.chdir(ROOT)

from app.api.app import create_app  # noqa: E402
from app.config.settings import get_settings  # noqa: E402

app = create_app()


def run() -> None:
    import uvicorn

    settings = get_settings()
    parser = argparse.ArgumentParser(description="FrameGenius API server")
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", type=int, default=settings.port)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    run()
