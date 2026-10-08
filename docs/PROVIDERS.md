# Providers

## LLM

| id | notes |
| --- | --- |
| `demo` | offline writer, no key |
| `openai` | also any OpenAI-compatible gateway via `openai_base_url` |
| `anthropic` | Claude |
| `google` | Gemini |
| `deepseek` | OpenAI-compatible |
| `ollama` | local |
| `moonshot` | Kimi |
| `qwen` | DashScope compatible endpoint |

## TTS

| id | notes |
| --- | --- |
| `edge` | free, word timings, default |
| `azure` | Speech key + region |
| `google` | Cloud TTS REST |
| `elevenlabs` | voice id |
| `siliconflow` | CosyVoice |
| `chatterbox` | self-hosted OpenAI-style `/v1/audio/speech` |

## Media

| id | notes |
| --- | --- |
| `local` | `resource/media` + template covers |
| `pexels` | `PEXELS_API_KEY` or `pexels_api_keys` |
| `pixabay` | `PIXABAY_API_KEY` |
| `coverr` | `COVERR_API_KEY` |

If a paid media provider fails, the pipeline falls back to the local library so the render still finishes.

## Upload

`upload-post` or empty (local receipt).
