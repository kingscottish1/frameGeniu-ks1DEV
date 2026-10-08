# Architecture

FrameGenius is a **multi-agent composition pipeline**, not a pixel-diffusion model.

```
topic / script
    → Writer agent        (LLM or demo templates)
    → Voice agent         (Edge TTS / Azure / ElevenLabs / …)
    → Media scout agent   (Pexels / Pixabay / Coverr / local Ken Burns)
    → Caption agent       (word timings → SRT + ASS)
    → Editor agent        (FFmpeg cut / grade / mix / burn)
    → Publisher agent     (thumbnail + result envelope)
```

Conductor: `app/agents/orchestrator.py`

| Path | Role |
| --- | --- |
| `app/agents/` | six specialist agents + conductor |
| `dashboard/` | cinematic studio UI |
| `main.py` + `app/api/` | FastAPI |
| `cli.py` | Typer CLI |
| `app/providers/` | vendor adapters |
| `app/security/` | AES-256-GCM vault, auth, hardening |

Author: **kingscottishDEV N.A.S**.
