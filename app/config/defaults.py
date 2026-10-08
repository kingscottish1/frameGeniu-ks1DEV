"""Hard defaults used when config.toml is incomplete."""

from __future__ import annotations

DEFAULT_SYSTEM_PROMPT = """You are FrameGenius, an elite short-form video writer created by kingscottishDEV N.A.S.
Write spoken narration that sounds natural when read aloud. Keep sentences short.
Return ONLY valid JSON with this shape:
{
  "title": "string",
  "description": "string",
  "hook": "string",
  "language": "en",
  "scenes": [
    {
      "narration": "spoken sentence",
      "search": "stock footage keywords",
      "visual": "what the viewer should see",
      "duration": 4.0
    }
  ]
}
Rules:
- 5 to 10 scenes
- total spoken length around the requested duration
- search terms must be concrete visual nouns, never abstract ideas
- no markdown, no commentary
"""

DEFAULT_VOICES = [
    "en-GB-LibbyNeural",
    "en-GB-RyanNeural",
    "en-GB-ThomasNeural",
    "en-GB-SoniaNeural",
    "en-GB-MaisieNeural",
    "en-US-JennyNeural",
    "en-US-GuyNeural",
    "en-US-AriaNeural",
    "en-US-AndrewNeural",
    "en-AU-NatashaNeural",
    "en-IN-NeerjaNeural",
    "nl-NL-ColetteNeural",
    "nl-NL-MaartenNeural",
    "de-DE-KatjaNeural",
    "fr-FR-DeniseNeural",
    "es-ES-ElviraNeural",
    "pt-BR-FranciscaNeural",
    "ja-JP-NanamiNeural",
    "zh-CN-XiaoxiaoNeural",
]

ASPECT_PRESETS = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
    "21:9": (1920, 824),
}

LLM_PROVIDERS = ["auto", "studio", "ollama", "openai", "anthropic", "google", "deepseek", "moonshot", "qwen"]
TTS_PROVIDERS = ["edge", "azure", "google", "elevenlabs", "siliconflow", "chatterbox"]
MEDIA_PROVIDERS = ["local", "coverr", "pexels", "pixabay", "web"]
COLOR_GRADES = ["none", "cinematic", "vivid", "moody"]
