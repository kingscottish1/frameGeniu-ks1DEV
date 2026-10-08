"""Saved videos and scripts."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from app.services import task as task_service
from app.services import upload as upload_service
from webui.components.config_form import page_setup
from webui.components.video_preview import show_video

page_setup("Library")
st.markdown("<div class='fg-kicker'>Archive</div>", unsafe_allow_html=True)
st.title("Library")

tasks = [item for item in task_service.list_tasks() if item.state.value == "completed"]
if not tasks:
    st.info("Finished videos will land here.")
    st.stop()

for record in tasks:
    left, right = st.columns((0.42, 0.58))
    with left:
        thumb = Path(record.result.get("thumbnail_path") or "")
        if thumb.exists():
            st.image(str(thumb), use_container_width=True)
        st.markdown(f"**{record.result.get('title') or record.params.get('topic')}**")
        st.caption(record.task_id)
    with right:
        video = record.result.get("video_path")
        if video:
            show_video(video)
        if st.button("Prepare publish receipt", key=f"pub-{record.task_id}"):
            receipt = upload_service.publish(
                video,
                title=str(record.result.get("title") or "FrameGenius"),
                description=str(record.params.get("topic") or ""),
            )
            st.json(receipt)
    st.markdown("<hr class='fg-hr' />", unsafe_allow_html=True)
