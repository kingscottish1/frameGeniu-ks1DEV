"""DeepSeek — OpenAI-compatible."""

from __future__ import annotations

from app.providers.llm.openai import OpenAILLM


class DeepSeekLLM(OpenAILLM):
    name = "deepseek"

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-chat",
        base_url: str = "https://api.deepseek.com",
        timeout: float = 90.0,
        **kwargs,
    ):
        super().__init__(api_key=api_key, model=model, base_url=base_url, timeout=timeout, **kwargs)
