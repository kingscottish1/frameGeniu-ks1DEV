"""Configuration page."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from app.config.defaults import LLM_PROVIDERS, MEDIA_PROVIDERS, TTS_PROVIDERS
from app.config.settings import get_settings, save_settings
from webui.components.config_form import page_setup

page_setup("Settings")
st.markdown("<div class='fg-kicker'>Control room</div>", unsafe_allow_html=True)
st.title("Settings")

settings = get_settings()

with st.form("cfg"):
    st.subheader("Language model")
    c1, c2 = st.columns(2)
    llm = c1.selectbox("Provider", LLM_PROVIDERS, index=max(0, LLM_PROVIDERS.index(settings.llm_provider) if settings.llm_provider in LLM_PROVIDERS else 0))
    openai_key = c2.text_input("OpenAI key", value=str(settings.llm.get("openai_api_key") or ""), type="password")
    c3, c4 = st.columns(2)
    openai_model = c3.text_input("OpenAI model", value=str(settings.llm.get("openai_model") or "gpt-4o-mini"))
    openai_base = c4.text_input("OpenAI base URL", value=str(settings.llm.get("openai_base_url") or ""))
    d1, d2 = st.columns(2)
    anthropic = d1.text_input("Anthropic key", value=str(settings.llm.get("anthropic_api_key") or ""), type="password")
    gemini = d2.text_input("Gemini key", value=str(settings.llm.get("google_api_key") or ""), type="password")
    e1, e2 = st.columns(2)
    deepseek = e1.text_input("DeepSeek key", value=str(settings.llm.get("deepseek_api_key") or ""), type="password")
    ollama = e2.text_input("Ollama URL", value=str(settings.llm.get("ollama_base_url") or "http://127.0.0.1:11434"))

    st.subheader("Voice")
    t1, t2 = st.columns(2)
    tts = t1.selectbox("TTS provider", TTS_PROVIDERS, index=max(0, TTS_PROVIDERS.index(settings.tts_provider) if settings.tts_provider in TTS_PROVIDERS else 0))
    voice = t2.text_input("Default voice", value=str(settings.tts.get("voice") or "en-US-JennyNeural"))
    eleven = st.text_input("ElevenLabs key", value=str(settings.tts.get("elevenlabs_api_key") or ""), type="password")

    st.subheader("Footage")
    m1, m2 = st.columns(2)
    media = m1.selectbox("Media provider", MEDIA_PROVIDERS, index=max(0, MEDIA_PROVIDERS.index(settings.media_provider) if settings.media_provider in MEDIA_PROVIDERS else 0))
    pexels = m2.text_input("Pexels key", value=",".join(settings.media.get("pexels_api_keys") or []), type="password")
    pixabay = st.text_input("Pixabay key", value=",".join(settings.media.get("pixabay_api_keys") or []), type="password")

    st.subheader("Picture")
    v1, v2, v3 = st.columns(3)
    aspect = v1.selectbox("Default aspect", ["9:16", "16:9", "1:1", "4:5"], index=0)
    grade = v2.selectbox("Color grade", ["cinematic", "vivid", "moody", "none"])
    crf = v3.slider("CRF (quality)", 14, 28, int(settings.video.get("crf") or 20))

    saved = st.form_submit_button("Save configuration", use_container_width=True)

if saved:
    save_settings(
        {
            "llm": {
                "provider": llm,
                "openai_api_key": openai_key,
                "openai_model": openai_model,
                "openai_base_url": openai_base,
                "anthropic_api_key": anthropic,
                "google_api_key": gemini,
                "deepseek_api_key": deepseek,
                "ollama_base_url": ollama,
            },
            "tts": {"provider": tts, "voice": voice, "elevenlabs_api_key": eleven},
            "media": {
                "provider": media,
                "pexels_api_keys": [part.strip() for part in pexels.split(",") if part.strip()],
                "pixabay_api_keys": [part.strip() for part in pixabay.split(",") if part.strip()],
            },
            "video": {"aspect_ratio": aspect, "color_grade": grade, "crf": crf},
        }
    )
    st.success("Saved. New renders will use these settings.")
    st.rerun()
