# Configuration

FrameGenius reads `config.toml` (copied from `config.example.toml` on first install).
Environment variables and `.env` override file values.

## Sections

| Section | Role |
| --- | --- |
| `[app]` | host, ports, concurrency, ffmpeg path, demo flag |
| `[llm]` | provider + keys + models |
| `[tts]` | Edge / Azure / Google / ElevenLabs / SiliconFlow / Chatterbox |
| `[media]` | Pexels / Pixabay / Coverr / local |
| `[video]` | aspect, CRF, grade, transitions |
| `[subtitle]` | font, size, colours, whisper vs edge timings |
| `[audio]` | BGM mix |
| `[whisper]` | local transcription |
| `[upload]` | Upload-Post |
| `[proxy]` | HTTP(S) proxy |
| `[webhooks]` | completion / failure callbacks |

## Demo mode

```toml
[llm]
provider = "demo"

[media]
provider = "local"

[tts]
provider = "edge"
```

This combination needs **zero paid keys**. Edge TTS still needs internet.

## Secrets

Prefer environment variables:

```
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
DEEPSEEK_API_KEY=
PEXELS_API_KEY=
ELEVENLABS_API_KEY=
```

The WebUI Settings page writes back into `config.toml`. Keys are redacted when the API returns config.
