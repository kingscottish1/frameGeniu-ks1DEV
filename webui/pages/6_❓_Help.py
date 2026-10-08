"""Help and documentation."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from app.utils.file_manager import ROOT
from webui.components.config_form import page_setup

page_setup("Help")
st.markdown("<div class='fg-kicker'>Manual</div>", unsafe_allow_html=True)
st.title("Help")

st.markdown(
    """
### First render in five minutes
1. Double-click `INSTALL.bat` (once).
2. Double-click `START.bat`.
3. Open **Generate**, type a topic, hit **Render video**.
4. Demo mode uses local stills + free Edge voices. No keys required.

### Keys (optional, better footage / writing)
- **Pexels** — https://www.pexels.com/api/
- **OpenAI / DeepSeek / Gemini / Claude / Ollama** — Settings page
- **ElevenLabs** — premium voices

### CLI
```
.venv\\Scripts\\python cli.py generate "Your topic" --aspect 9:16
.venv\\Scripts\\python cli.py list
```

### API
`POST /api/v1/videos` with a JSON body `{ "topic": "..." }`  
Swagger lives at `/docs`.

### FFmpeg
A binary is bundled via `imageio-ffmpeg`. System FFmpeg is used if present.

### Support
Built by **kingscottishDEV N.A.S**. MIT licensed.
    """
)

docs = ROOT / "docs"
if docs.exists():
    picks = sorted(docs.glob("*.md"))
    if picks:
        name = st.selectbox("Read a guide", [path.name for path in picks])
        st.markdown((docs / name).read_text(encoding="utf-8"))
