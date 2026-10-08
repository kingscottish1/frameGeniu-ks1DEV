"""Video templates library."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from app.utils.file_manager import ROOT
from webui.components.config_form import page_setup
from webui.components.templates import TEMPLATES

page_setup("Templates")
st.markdown("<div class='fg-kicker'>Look book</div>", unsafe_allow_html=True)
st.title("Templates")

covers = ROOT / "resource" / "templates" / "covers"
folder = ROOT / "resource" / "templates"

cols = st.columns(3)
for index, (key, title, blurb) in enumerate(TEMPLATES):
    with cols[index % 3]:
        cover = covers / f"{key}.jpg"
        if cover.exists():
            st.image(str(cover), use_container_width=True)
        spec = folder / f"{key}.json"
        st.markdown(f"### {title}")
        st.caption(blurb)
        if spec.exists():
            data = json.loads(spec.read_text(encoding="utf-8"))
            st.write(data.get("tagline") or data.get("description") or "")
            st.caption("Voice · " + str(data.get("voice") or "en-US-JennyNeural"))
        if st.button(f"Use {title}", key=f"use-{key}"):
            st.session_state["preferred_template"] = key
            st.success(f"{title} selected. Open Generate to render.")
