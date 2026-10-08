"""Anthropic Claude."""

from __future__ import annotations

from anthropic import Anthropic

from app.providers.llm.base import BaseLLM
from app.utils.exceptions import ProviderError


class AnthropicLLM(BaseLLM):
    name = "anthropic"

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-latest", timeout: float = 90.0, **kwargs):
        super().__init__(**kwargs)
        if not api_key:
            raise ProviderError("Anthropic API key is missing.", stage="llm")
        self.model = model
        self.client = Anthropic(api_key=api_key, timeout=timeout)

    def generate(self, prompt: str, *, system: str = "", temperature: float = 0.8, max_tokens: int = 2048) -> str:
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system or "You are FrameGenius.",
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            raise ProviderError(f"Anthropic request failed: {exc}", stage="llm") from exc
        chunks = []
        for block in message.content:
            text = getattr(block, "text", None)
            if text:
                chunks.append(text)
        text = "".join(chunks).strip()
        if not text:
            raise ProviderError("Anthropic returned an empty response.", stage="llm")
        return text
