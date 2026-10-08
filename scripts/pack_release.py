#!/usr/bin/env python3
"""Build a ready-to-run zip of FrameGenius.

Launchers sit at the ZIP ROOT (GO.bat / GO.cmd) so Windows Extract All
does not bury them in a nested FrameGenius\\FrameGenius folder.
"""

from __future__ import annotations

import shutil
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
NAME = "FrameGenius"

SKIP_DIRS = {
    ".venv",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".arena",
    "dist",
    ".test-data",
    ".streamlit",
}
SKIP_FILES = {".env", "config.toml", "uv.lock", "FrameGenius.zip", "HOW_TO_RUN.txt"}
SKIP_SUFFIX = {".pyc", ".pyo", ".wav", ".log", ".zip", ".gz"}
SKIP_PREFIXES = (
    "outputs/videos/",
    "outputs/scripts/",
    "outputs/logs/",
    "outputs/thumbnails/",
    "outputs/tasks/",
    "outputs/images/",
    "outputs/uploads/",
    "outputs/TODAY/",
    "outputs/posts/",
    "data/",
)

LAUNCHERS = (
    "GO.bat",
    "GO.cmd",
    "APP.bat",
    "APP.cmd",
    "INSTALL.bat",
    "INSTALL.cmd",
    "RUN.bat",
    "RUN.cmd",
    "START_HERE.txt",
)


def wanted(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
        return False
    if path.name in SKIP_FILES:
        return False
    if path.name.startswith("PATCH_"):
        return False
    if path.suffix.lower() in SKIP_SUFFIX:
        return False
    if path.name == ".gitkeep":
        return True
    if any(rel.startswith(prefix) for prefix in SKIP_PREFIXES):
        return False
    return True


def files() -> list[Path]:
    return [item for item in ROOT.rglob("*") if item.is_file() and wanted(item)]


def _crlf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")


def extra_payload() -> dict[str, bytes]:
    extras: dict[str, bytes] = {}
    example = ROOT / "config.example.toml"
    if example.exists():
        extras["config.toml"] = example.read_bytes()
    # Always inject launchers even if a filter dropped them.
    for name in LAUNCHERS:
        path = ROOT / name
        if path.exists():
            extras[name] = path.read_bytes()
    return extras


def main() -> int:
    DIST.mkdir(exist_ok=True)
    bundle = files()
    extras = extra_payload()
    zip_path = DIST / f"{NAME}.zip"
    tar_path = DIST / f"{NAME}.tar.gz"
    home_zip = ROOT.parent / "FrameGenius.zip"
    home_tar = ROOT.parent / "FrameGenius.tar.gz"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        packed = set()
        for item in bundle:
            arc = item.relative_to(ROOT).as_posix()
            raw = item.read_bytes()
            if item.suffix.lower() in {".bat", ".cmd"} or item.name in {"START_HERE.txt"}:
                zf.writestr(arc, _crlf(raw))
            else:
                zf.writestr(arc, raw)
            packed.add(arc)
        for name, data in extras.items():
            if name in packed:
                continue
            payload = _crlf(data) if name.lower().endswith((".bat", ".cmd", ".txt")) else data
            zf.writestr(name, payload)
            packed.add(name)

    missing = [name for name in ("GO.bat", "GO.cmd", "APP.cmd", "INSTALL.cmd", "RUN.cmd") if name not in packed]
    if missing:
        raise SystemExit(f"pack_release refused: launchers missing from zip: {missing}")

    with tarfile.open(tar_path, "w:gz") as tf:
        for item in bundle:
            tf.add(item, item.relative_to(ROOT))
        staging = DIST / "_payload"
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir()
        for name, data in extras.items():
            dest = staging / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            tf.add(dest, name)
        shutil.rmtree(staging)

    shutil.copy2(zip_path, home_zip)
    shutil.copy2(tar_path, home_tar)

    with zipfile.ZipFile(home_zip) as zf:
        names = zf.namelist()
        print("LAUNCHERS IN ZIP:")
        for n in names:
            if n.upper().startswith(("GO.", "APP.", "INSTALL.", "RUN.")):
                print(" ", n, zf.getinfo(n).file_size)
    print(zip_path, zip_path.stat().st_size)
    print(home_zip, home_zip.stat().st_size)
    print(f"{len(bundle) + len(extras)} files packed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
