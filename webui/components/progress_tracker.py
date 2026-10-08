"""Task progress display."""

from __future__ import annotations

import streamlit as st

from app.models.task import TaskRecord


def render_progress(record: TaskRecord | None) -> None:
    if not record:
        return
    st.progress(max(0, min(100, record.progress)) / 100.0, text=f"{record.stage} · {record.progress}%")
    if record.message:
        st.caption(record.message)
    if record.state.value == "failed" and record.error:
        st.error(record.error)
    if record.state.value == "completed":
        st.success("Render complete.")
