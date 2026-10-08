---
name: framegenius
description: Generate short-form videos with FrameGenius (script, TTS, stock footage, captions, FFmpeg render). Use when the user wants a YouTube Short, TikTok, Reel, or narrated montage from a topic.
metadata:
  author: kingscottishDEV N.A.S
  version: "1.0.0"
  product: FrameGenius
---

# FrameGenius skill

## When to use

The user wants a finished vertical or landscape short from a topic or a script.

## Preconditions

- FrameGenius is installed.
- API is running on `http://127.0.0.1:8080` or the CLI is available.

## Workflow

1. Confirm topic, aspect (`9:16` default), duration (~30s), language, template.
2. Prefer CLI for a single shot:

```bash
python cli.py generate "TOPIC" --aspect 9:16 --duration 30 --template motivational
```

3. Or POST `/api/v1/videos` then poll `/api/v1/tasks/{id}` until `completed`.
4. Return the MP4 path from `result.video_path`. Do not claim the video is published unless upload was requested and succeeded.

## Rules

- Do not invent API keys.
- Demo mode is valid. Mention it if no LLM / Pexels key is configured.
- Keep custom scripts spoken-word, not essay-length.
- Search terms must be concrete visuals.
