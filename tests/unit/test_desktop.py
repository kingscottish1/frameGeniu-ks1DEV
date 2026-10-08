from pathlib import Path

import desktop


def test_desktop_module_has_window_helpers():
    assert desktop.URL.startswith("http://127.0.0.1:")
    assert callable(desktop._open_window)
    assert callable(desktop._browser_app)


def test_app_launchers_exist():
    root = Path(__file__).resolve().parents[2]
    assert (root / "APP.cmd").exists()
    assert (root / "APP.bat").exists()
    assert (root / "desktop.py").exists()
    text = (root / "APP.cmd").read_text(encoding="utf-8", errors="ignore")
    assert "desktop.py" in text
