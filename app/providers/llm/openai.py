"""OpenAI and any OpenAI-compatible chat API."""

from __future__ import annotations

from openai import OpenAI

from app.providers.llm.base import BaseLLM
from app.utils.exceptions import ProviderError


class OpenAILLM(BaseLLM):
    name = "openai"

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
        timeout: float = 90.0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if not api_key:
            raise ProviderError("OpenAI API key is missing.", stage="llm")
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url or None, timeout=timeout)

    def generate(self, prompt: str, *, system: str = "", temperature: float = 0.8, max_tokens: int = 2048) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            raise ProviderError(f"OpenAI request failed: {exc}", stage="llm") from exc
        text = (response.choices[0].message.content or "").strip()
        if not text:
            raise ProviderError("OpenAI returned an empty response.", stage="llm")
        return text
