"""Google Gemini."""

from __future__ import annotations

from app.providers.llm.base import BaseLLM
from app.utils.exceptions import ProviderError


class GoogleLLM(BaseLLM):
    name = "google"

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash", **kwargs):
        super().__init__(**kwargs)
        if not api_key:
            raise ProviderError("Google Gemini API key is missing.", stage="llm")
        try:
            import google.generativeai as genai
        except Exception as exc:  # pragma: no cover
            raise ProviderError(f"google-generativeai is not installed: {exc}", stage="llm") from exc
        self.model_name = model
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)

    def generate(self, prompt: str, *, system: str = "", temperature: float = 0.8, max_tokens: int = 2048) -> str:
        body = prompt if not system else f"{system}\n\n{prompt}"
        try:
            response = self.model.generate_content(
                body,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                },
            )
        except Exception as exc:
            raise ProviderError(f"Gemini request failed: {exc}", stage="llm") from exc
        text = (getattr(response, "text", None) or "").strip()
        if not text:
            raise ProviderError("Gemini returned an empty response.", stage="llm")
        return text
