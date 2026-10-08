"""Local Ollama models.

Writer default: 17GB uncensored Gemma.
Crown: gemma4-pro — the others were not answering.
Never name the model in the UI.
"""

STUDIO_MODELS = [
    "gemma4-pro:latest",
    "gemma4:latest",
    "1stageze/gemma4-26b-uncensored-1m:latest",
    "dzgg/Qwen3.5-Uncensored-HauhauCS-Aggressive:4b",
    "qwen3.5-direct:latest",
    "qwen3-8b-pro:latest",
    "qwen3.6-pro:latest",
    "qwen-coder-fast:latest",
    "qwen2.5-coder:1.5b-base",
]

PREFERRED_MODELS = tuple(STUDIO_MODELS)

DEFAULT_OLLAMA_MODEL = "1stageze/gemma4-26b-uncensored-1m:latest"
CROWN_MODEL = "gemma4-pro:latest"
CROWN_FALLBACKS = (
    "gemma4-pro:latest",
    "gemma4-pro",
    "gemma4:latest",
)
