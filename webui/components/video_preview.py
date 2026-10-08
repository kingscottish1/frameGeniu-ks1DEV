"""Video preview widget."""

from __future__ import annotations

from pathlib import Path

import streamlit as st


def show_video(path: str | Path | None, *, title: str | None = None) -> None:
    if not path:
        st.info("No video yet.")
        return
    file = Path(path)
    if not file.exists():
        st.warning(f"Missing file: {file}")
        return
    if title:
        st.markdown(f"**{title}**")
    st.video(str(file))
    st.download_button("Download MP4", data=file.read_bytes(), file_name=file.name, mime="video/mp4")
