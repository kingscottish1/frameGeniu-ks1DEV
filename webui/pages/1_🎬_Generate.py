"""Main video generation page."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import time

import streamlit as st

from app.config.defaults import DEFAULT_VOICES
from app.models.video import AspectRatio, VideoParams
from app.services import task as task_service
from webui.components.config_form import page_setup
from webui.components.progress_tracker import render_progress
from webui.components.video_preview import show_video

page_setup("Generate")

st.markdown("<div class='fg-kicker'>Create</div>", unsafe_allow_html=True)
st.title("Generate a short")

col_form, col_out = st.columns((1.05, 0.95), gap="large")

with col_form:
    topic = st.text_input("Topic", placeholder="Why cold plunges actually work")
    script_text = st.text_area("Custom script (optional)", height=140, placeholder="Leave empty to let FrameGenius write it.")
    c1, c2, c3 = st.columns(3)
    template = c1.selectbox("Template", ["motivational", "educational", "entertainment", "product", "story", "news"])
    aspect = c2.selectbox("Aspect", ["9:16", "16:9", "1:1", "4:5"])
    language = c3.selectbox("Language", ["en", "nl", "de", "fr", "es", "pt", "ja", "zh"])
    d1, d2 = st.columns(2)
    duration = d1.slider("Target length (seconds)", 10, 90, 30)
    voice = d2.selectbox("Voice", DEFAULT_VOICES)
    e1, e2, e3 = st.columns(3)
    subtitles = e1.toggle("Captions", True)
    bgm = e2.toggle("Background music", True)
    grade = e3.selectbox("Grade", ["cinematic", "vivid", "moody", "none"])
    go = st.button("Render video", use_container_width=True)

with col_out:
    st.markdown("### Monitor")
    placeholder = st.empty()

if go:
    if not topic.strip():
        st.error("Give me a topic first.")
        st.stop()
    params = VideoParams(
        topic=topic.strip(),
        script_text=script_text.strip() or None,
        template=template,
        aspect_ratio=AspectRatio(aspect),
        language=language,
        duration=float(duration),
        voice=voice,
        subtitle_enabled=subtitles,
        bgm_enabled=bgm,
        color_grade=grade,
    )
    record = task_service.submit(params)
    st.session_state["active_task"] = record.task_id

task_id = st.session_state.get("active_task")
if task_id:
    live = placeholder.container()
    for _ in range(240):
        record = task_service.get_task(task_id)
        with live:
            if record:
                render_progress(record)
                if record.state.value == "completed":
                    show_video(record.result.get("video_path"), title=record.result.get("title"))
                    break
                if record.state.value in {"failed", "cancelled"}:
                    break
        time.sleep(1.1)
        if record and record.state.value in {"completed", "failed", "cancelled"}:
            break
