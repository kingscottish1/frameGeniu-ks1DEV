"""LLM provider abstraction used by script generation."""

from __future__ import annotations

from app.providers.llm import BaseLLM, create_llm


def get_llm(provider: str | None = None) -> BaseLLM:
    return create_llm(provider)


def complete(
    prompt: str,
    *,
    provider: str | None = None,
    system: str = "",
    temperature: float = 0.8,
    max_tokens: int = 2048,
    model: str | None = None,
) -> str:
    llm = get_llm(provider)
    if model and getattr(llm, "pick_model", None):
        try:
            llm.model = llm.pick_model(model)
        except Exception:
            llm.model = model
    elif model:
        llm.model = model
    return llm.generate(prompt, system=system, temperature=temperature, max_tokens=max_tokens)
