"""Template selector cards."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from app.utils.file_manager import ROOT

COVERS = ROOT / "resource" / "templates" / "covers"

TEMPLATES = [
    ("motivational", "Motivational", "Punchy voice. Big feelings. Call to action."),
    ("educational", "Educational", "Clear structure. Teach one idea well."),
    ("entertainment", "Entertainment", "Hooks, twists, internet energy."),
    ("product", "Product", "Problem, product, proof, ship it."),
    ("story", "Story", "Personal arc. Quiet honesty."),
    ("news", "News brief", "Signal over noise. Calm authority."),
    ("crime", "Crime deep dive", "Last 24 hours. Paper trail. Who lied."),
]


def template_cards(current: str | None = None) -> str:
    cols = st.columns(3)
    picked = current or "motivational"
    for index, (key, title, blurb) in enumerate(TEMPLATES):
        with cols[index % 3]:
            cover = COVERS / f"{key}.jpg"
            if cover.exists():
                st.image(str(cover), use_container_width=True)
            st.markdown(f"**{title}**")
            st.caption(blurb)
            if st.button("Use" if picked != key else "Selected", key=f"tpl-{key}"):
                picked = key
    return picked
