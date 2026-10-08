#!/usr/bin/env python3
"""FrameGenius desktop app — same studio, native window. No extra paid software.

Windows: Edge/Chrome --app window (no tabs, no address bar).
If pywebview is installed it uses that instead.
If the studio is already running on 8080, this just opens the window.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

HOST = "127.0.0.1"
PORT = int(os.environ.get("FRAMEGENIUS_PORT") or 8080)
URL = f"http://{HOST}:{PORT}"


def _port_open() -> bool:
    sock = socket.socket()
    sock.settimeout(0.35)
    try:
        sock.connect((HOST, PORT))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def _start_server() -> None:
    import uvicorn

    from main import app

    config = uvicorn.Config(app, host=HOST, port=PORT, log_level="info")
    uvicorn.Server(config).run()


def _wait_ready(seconds: float = 45.0) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if _port_open():
            return True
        time.sleep(0.2)
    return False


def _browser_app() -> str | None:
    env = os.environ
    candidates = [
        env.get("PROGRAMFILES", "") + r"\Microsoft\Edge\Application\msedge.exe",
        env.get("PROGRAMFILES(X86)", "") + r"\Microsoft\Edge\Application\msedge.exe",
        env.get("LOCALAPPDATA", "") + r"\Microsoft\Edge\Application\msedge.exe",
        env.get("PROGRAMFILES", "") + r"\Google\Chrome\Application\chrome.exe",
        env.get("LOCALAPPDATA", "") + r"\Google\Chrome\Application\chrome.exe",
        env.get("PROGRAMFILES", "") + r"\BraveSoftware\Brave-Browser\Application\brave.exe",
    ]
    for path in candidates:
        if path and Path(path).exists():
            return path
    return None


def _open_window() -> str:
    try:
        import webview  # type: ignore

        webview.create_window(
            "FrameGenius · Crown AI",
            URL,
            width=1440,
            height=920,
            min_size=(980, 680),
        )
        webview.start()
        return "webview"
    except Exception:
        pass

    exe = _browser_app()
    if exe:
        profile = ROOT / "outputs" / ".app-profile"
        profile.mkdir(parents=True, exist_ok=True)
        cmd = [
            exe,
            f"--app={URL}",
            f"--user-data-dir={str(profile)}",
            "--no-first-run",
            "--no-default-browser-check",
            "--window-size=1440,920",
        ]
        print(f"Opening FrameGenius app window…")
        proc = subprocess.Popen(cmd)
        proc.wait()
        return "app"
    webbrowser.open(URL)
    return "browser"


def main() -> int:
    started_here = False
    if not _port_open():
        thread = threading.Thread(target=_start_server, name="fg-server", daemon=True)
        thread.start()
        started_here = True
        if not _wait_ready():
            print("FrameGenius did not start on", URL)
            return 1
    else:
        print("Studio already running — opening the app window.")

    mode = _open_window()
    if mode == "browser":
        print("Opened in your browser:", URL)
        print("Close this window to stop the studio.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
