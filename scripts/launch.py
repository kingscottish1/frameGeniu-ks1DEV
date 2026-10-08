#!/usr/bin/env python3
"""Launch FrameGenius API, WebUI, or both.

Used by START.bat / webui.sh — kingscottishDEV N.A.S
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ["PYTHONPATH"] = str(ROOT) + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")

from app.config.settings import get_settings  # noqa: E402


def _python() -> str:
    return sys.executable


def start_api(host: str, port: int) -> subprocess.Popen:
    return subprocess.Popen(
        [_python(), str(ROOT / "main.py"), "--host", host, "--port", str(port)],
        cwd=str(ROOT),
    )


def start_webui(host: str, port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env["BROWSER"] = "none"
    return subprocess.Popen(
        [
            _python(),
            "-m",
            "streamlit",
            "run",
            str(ROOT / "webui" / "streamlit_app.py"),
            "--server.address",
            host,
            "--server.port",
            str(port),
            "--server.headless",
            "true",
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=str(ROOT),
        env=env,
    )


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="FrameGenius launcher")
    parser.add_argument("--api", action="store_true")
    parser.add_argument("--webui", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--api-port", type=int, default=settings.port)
    parser.add_argument("--webui-port", type=int, default=settings.webui_port)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not (args.api or args.webui or args.all):
        args.all = True

    children: list[subprocess.Popen] = []

    def shutdown(*_signal) -> None:
        for child in children:
            if child.poll() is None:
                child.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    if args.api or args.all:
        print(f"  API     http://127.0.0.1:{args.api_port}")
        print(f"  Docs    http://127.0.0.1:{args.api_port}/docs")
        children.append(start_api(args.host, args.api_port))
    if args.webui or args.all:
        print(f"  Studio  http://127.0.0.1:{args.webui_port}")
        children.append(start_webui(args.host, args.webui_port))
        if not args.no_browser:
            time.sleep(2.2)
            try:
                webbrowser.open(f"http://127.0.0.1:{args.webui_port}")
            except Exception:
                pass

    print("  FrameGenius is running. Press Ctrl+C to stop.")
    while True:
        for child in children:
            code = child.poll()
            if code is not None:
                print(f"  A child process exited ({code}). Shutting down.")
                shutdown()
        time.sleep(0.6)


if __name__ == "__main__":
    raise SystemExit(main())
