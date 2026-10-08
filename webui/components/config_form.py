"""Shared page chrome and theme injection."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from app import __author__, __version__
from app.config.settings import get_settings
from app.utils.file_manager import ROOT

STYLES = ROOT / "webui" / "styles"
LOGO = ROOT / "resource" / "icons" / "logo.png"
WORDMARK = ROOT / "resource" / "icons" / "logo-wordmark.png"


def inject_theme() -> None:
    css_parts = []
    for name in ("main.css", "dark_theme.css"):
        path = STYLES / name
        if path.exists():
            css_parts.append(path.read_text(encoding="utf-8"))
    if css_parts:
        st.markdown(f"<style>{''.join(css_parts)}</style>", unsafe_allow_html=True)


def page_setup(title: str, icon: str = "🎬") -> None:
    st.set_page_config(
        page_title=f"{title} · FrameGenius",
        page_icon=str(LOGO) if LOGO.exists() else icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_theme()
    with st.sidebar:
        if WORDMARK.exists():
            st.image(str(WORDMARK), use_container_width=True)
        elif LOGO.exists():
            st.image(str(LOGO), use_container_width=True)
        st.markdown(
            f"<div class='fg-kicker'>Studio v{__version__}</div>"
            f"<p class='fg-muted' style='margin-top:0.35rem'>{__author__}</p>",
            unsafe_allow_html=True,
        )
        settings = get_settings()
        st.caption(
            f"LLM · {settings.llm_provider}  \n"
            f"TTS · {settings.tts_provider}  \n"
            f"Media · {settings.media_provider}"
        )
        st.markdown("<hr class='fg-hr' />", unsafe_allow_html=True)
