"""Alibaba Qwen (DashScope OpenAI-compatible)."""

from __future__ import annotations

from app.providers.llm.openai import OpenAILLM


class QwenLLM(OpenAILLM):
    name = "qwen"

    def __init__(
        self,
        api_key: str,
        model: str = "qwen-plus",
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        timeout: float = 90.0,
        **kwargs,
    ):
        super().__init__(api_key=api_key, model=model, base_url=base_url, timeout=timeout, **kwargs)
