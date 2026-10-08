"""Base LLM interface."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLLM(ABC):
    name = "base"

    def __init__(self, **kwargs):
        self.options = kwargs

    @abstractmethod
    def generate(self, prompt: str, *, system: str = "", temperature: float = 0.8, max_tokens: int = 2048) -> str:
        raise NotImplementedError

    def chat(self, messages: list[dict], *, system: str = "", temperature: float = 0.8, max_tokens: int = 2048) -> str:
        blob = "\n".join(f"{item.get('role', 'user')}: {item.get('content', '')}" for item in messages)
        return self.generate(blob, system=system, temperature=temperature, max_tokens=max_tokens)

    def ping(self) -> bool:
        return True


class DemoLLM(BaseLLM):
    """Offline talker when Ollama is down — still draws via the imagine step."""

    name = "demo"

    def generate(self, prompt: str, *, system: str = "", temperature: float = 0.8, max_tokens: int = 2048) -> str:
        return self.chat([{"role": "user", "content": prompt}], system=system, temperature=temperature, max_tokens=max_tokens)

    def chat(self, messages: list[dict], *, system: str = "", temperature: float = 0.8, max_tokens: int = 2048) -> str:
        last = ""
        for item in reversed(messages or []):
            if (item.get("role") or "user") == "user" and item.get("content"):
                last = str(item["content"]).strip()
                break
        low = last.lower()
        if any(w in low for w in ("draw", "picture", "image", "photo", "paint", "pic")):
            return "On it — generating that now."
        if any(w in low for w in ("hello", "hi ", "hey", "what's up", "what can you")):
            return (
                "Hey. I'm Crown. Ideas, questions, or tell me what to paint "
                "and I'll make a real picture."
            )
        if last:
            return (
                "Ollama isn't running on this machine, so I'm on backup chat. "
                "I can still paint pictures — describe the shot. "
                "For a full film, use Generate."
            )
        return "I'm Crown. What should we talk about, or what should I paint?"
