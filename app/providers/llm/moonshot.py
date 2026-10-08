"""Moonshot / Kimi — OpenAI-compatible."""

from __future__ import annotations

from app.providers.llm.openai import OpenAILLM


class MoonshotLLM(OpenAILLM):
    name = "moonshot"

    def __init__(
        self,
        api_key: str,
        model: str = "moonshot-v1-8k",
        base_url: str = "https://api.moonshot.cn/v1",
        timeout: float = 90.0,
        **kwargs,
    ):
        super().__init__(api_key=api_key, model=model, base_url=base_url, timeout=timeout, **kwargs)
