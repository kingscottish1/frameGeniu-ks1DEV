"""Loguru logging setup."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

_CONFIGURED = False


def setup_logging(log_dir: str | Path | None = None, *, debug: bool = False, hide_log: bool = False) -> None:
    global _CONFIGURED
    logger.remove()
    level = "DEBUG" if debug else "INFO"
    if not hide_log:
        logger.add(
            sys.stderr,
            level=level,
            colorize=True,
            format=(
                "<dim>{time:HH:mm:ss}</dim> "
                "<level>{level: <8}</level> "
                "<cyan>{name}</cyan> · {message}"
            ),
        )
    if log_dir:
        path = Path(log_dir)
        path.mkdir(parents=True, exist_ok=True)
        logger.add(
            path / "framegenius.log",
            rotation="12 MB",
            retention="14 days",
            level="DEBUG",
            encoding="utf-8",
            enqueue=True,
        )
    _CONFIGURED = True


def get_logger(name: str | None = None):
    if not _CONFIGURED:
        setup_logging()
    return logger.bind(name=name or "framegenius")
