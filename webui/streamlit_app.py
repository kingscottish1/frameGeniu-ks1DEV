"""FrameGenius home — kingscottishDEV N.A.S."""

from __future__ import annotations

from pathlib import Path

import bootstrap  # noqa: F401
import streamlit as st

from app import __author__, __version__
from app.config.settings import get_settings
from app.services import task as task_service
from app.utils.file_manager import ROOT
from webui.components.config_form import page_setup

page_setup("Home", "🎬")

HERO = ROOT / "resource" / "icons" / "hero-art.png"
WORDMARK = ROOT / "resource" / "icons" / "logo-wordmark.png"
OG = ROOT / "resource" / "icons" / "og-banner.png"

if HERO.exists():
    st.image(str(HERO), use_container_width=True)
elif OG.exists():
    st.image(str(OG), use_container_width=True)

st.markdown(
    f"""
    <div style="margin-top:1rem">
      <div class="fg-kicker">AI Video Generation Studio</div>
      <h1 style="margin:0.2rem 0 0.4rem;font-size:3.1rem">Cut the film. Skip the busywork.</h1>
      <p class="fg-muted" style="max-width:46rem;font-size:1.05rem">
        FrameGenius writes the script, speaks the voice, finds the footage, burns the captions,
        and hands you a finished short. Built by {__author__}. Version {__version__}.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

c1, c2, c3, c4 = st.columns(4)
settings = get_settings()
tasks = task_service.list_tasks()
done = [item for item in tasks if item.state.value == "completed"]
failed = [item for item in tasks if item.state.value == "failed"]
c1.metric("Renders", len(done))
c2.metric("In flight", len([item for item in tasks if item.state.value == "processing"]))
c3.metric("Failed", len(failed))
c4.metric("LLM", settings.llm_provider)

st.markdown("<hr class='fg-hr' />", unsafe_allow_html=True)

left, right = st.columns((1.15, 0.85), gap="large")
with left:
    st.markdown("### How it works")
    st.markdown(
        """
1. **Write** — topic, or paste your own script  
2. **Speak** — Edge TTS is free; swap Azure / ElevenLabs later  
3. **See** — Pexels / Pixabay / Coverr, or the built-in local library  
4. **Cut** — FFmpeg grades, fades, captions, music  
5. **Ship** — download the MP4 or hand it to Upload-Post  
        """
    )
    st.page_link("pages/1_🎬_Generate.py", label="Open the generator", icon="🎬")
    st.page_link("pages/2_⚙️_Settings.py", label="Configure providers", icon="⚙️")

with right:
    st.markdown("### Studio status")
    st.markdown(
        f"""
<div class="fg-card">
  <div class="fg-pill">ready</div>
  <p style="margin:0.7rem 0 0.2rem"><b>Demo mode works with zero keys.</b></p>
  <p class="fg-muted">Local Ken Burns stills + Edge neural voices + cinematic grade.
  Add a Pexels key and an LLM key when you want more range.</p>
  <p class="fg-muted">API docs live at <code>http://127.0.0.1:{settings.port}/docs</code></p>
</div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<hr class='fg-hr' />", unsafe_allow_html=True)
st.caption(f"© 2026 {__author__}  ·  MIT License  ·  FrameGenius {__version__}")
