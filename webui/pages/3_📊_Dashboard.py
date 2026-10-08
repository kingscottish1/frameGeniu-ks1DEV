"""Analytics and task monitoring."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from app.services import task as task_service
from webui.components.config_form import page_setup
from webui.components.progress_tracker import render_progress

page_setup("Dashboard")
st.markdown("<div class='fg-kicker'>Monitor</div>", unsafe_allow_html=True)
st.title("Dashboard")

tasks = task_service.list_tasks()
done = [item for item in tasks if item.state.value == "completed"]
fail = [item for item in tasks if item.state.value == "failed"]
busy = [item for item in tasks if item.state.value == "processing"]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total jobs", len(tasks))
c2.metric("Completed", len(done))
c3.metric("Rendering", len(busy))
c4.metric("Failed", len(fail))

st.markdown("### Queue")
if not tasks:
    st.info("No tasks yet. Generate your first short.")
else:
    for record in tasks[:40]:
        with st.expander(f"{record.task_id}  ·  {record.params.get('topic', '')}  ·  {record.state.value}", expanded=record.state.value == "processing"):
            render_progress(record)
            if record.result.get("video_path"):
                st.code(record.result["video_path"])
            cols = st.columns(3)
            if cols[0].button("Refresh", key=f"r-{record.task_id}"):
                st.rerun()
            if record.state.value != "processing" and cols[1].button("Delete", key=f"d-{record.task_id}"):
                task_service.delete_task(record.task_id)
                st.rerun()
