"""Local Ollama — uses the models you already pulled."""

from __future__ import annotations

import httpx

from app.config.ollama_models import DEFAULT_OLLAMA_MODEL, PREFERRED_MODELS
from app.providers.llm.base import BaseLLM
from app.utils.exceptions import ProviderError

import re as _re

_THINK = _re.compile(r"<think>[\s\S]*?</think>", _re.I)


def _strip_think(text: str) -> str:
    return _THINK.sub("", text or "").strip()


def _stem(name: str) -> str:
    return (name or "").lower().strip().split(":")[0]


def _ctx_for(model: str) -> int:
    """Cap context so the 1M-ctx 26b brain does not try to load a million tokens."""
    low = (model or "").lower()
    if "1stageze" in low or "26b" in low or "1m" in low:
        return 32768
    if "qwen3.6" in low or "23" in low:
        return 8192
    return 8192


class OllamaLLM(BaseLLM):
    name = "ollama"

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        model: str = DEFAULT_OLLAMA_MODEL,
        timeout: float = 300.0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.base_url = base_url.rstrip("/")
        self.model = model or DEFAULT_OLLAMA_MODEL
        self.timeout = timeout
        self.num_ctx = int(kwargs.get("num_ctx") or 0)

    def list_models(self) -> list[str]:
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            payload = response.json()
        except Exception:
            return []
        names = []
        for item in payload.get("models") or []:
            name = str(item.get("name") or item.get("model") or "").strip()
            if name:
                names.append(name)
        return names

    def pick_model(self, requested: str | None = None) -> str:
        """Exact / stem match only. Never pick 1stageze/gemma4-... because someone asked for gemma4."""
        installed = self.list_models()
        if not installed:
            return (requested or DEFAULT_OLLAMA_MODEL).strip() or DEFAULT_OLLAMA_MODEL

        lowered = {name.lower(): name for name in installed}

        if requested and requested.strip():
            req = requested.strip()
            req_l = req.lower()
            if req_l in lowered:
                return lowered[req_l]
            req_stem = _stem(req)
            # Prefer the short name (gemma4:latest) over a namespaced clone.
            for name in installed:
                if _stem(name) == req_stem and "/" not in name:
                    return name
            for name in installed:
                if _stem(name) == req_stem:
                    return name
            for name in installed:
                if name.lower().startswith(req_l):
                    return name
            return req

        for prefer in PREFERRED_MODELS:
            if prefer.lower() in lowered:
                return lowered[prefer.lower()]
        for prefer in PREFERRED_MODELS:
            ps = _stem(prefer)
            for name in installed:
                if _stem(name) == ps and "/" not in name:
                    return name
            for name in installed:
                if _stem(name) == ps:
                    return name
        default_l = DEFAULT_OLLAMA_MODEL.lower()
        if default_l in lowered:
            return lowered[default_l]
        return installed[0]

    def chat(self, messages: list[dict], *, system: str = "", temperature: float = 0.8, max_tokens: int = 2048) -> str:
        model = self.pick_model(self.model)
        options = {"temperature": temperature, "num_predict": int(max_tokens)}
        ctx = int(self.num_ctx or _ctx_for(model))
        if ctx:
            options["num_ctx"] = ctx
        payload = {
            "model": model,
            "stream": False,
            "keep_alive": "15m",
            "options": options,
            "messages": [],
        }
        if system:
            payload["messages"].append({"role": "system", "content": system})
        for item in messages:
            role = item.get("role") or "user"
            content = str(item.get("content") or "").strip()
            if content:
                payload["messages"].append({"role": role, "content": content})
        try:
            response = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise ProviderError(f"Ollama request failed: {exc}", stage="llm") from exc
        text = str((data.get("message") or {}).get("content") or "").strip()
        text = _strip_think(text)
        if not text:
            raise ProviderError("Ollama returned an empty response.", stage="llm")
        return text

    def generate(self, prompt: str, *, system: str = "", temperature: float = 0.8, max_tokens: int = 2048) -> str:
        return self.chat([{"role": "user", "content": prompt}], system=system, temperature=temperature, max_tokens=max_tokens)

    def ping(self) -> bool:
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
