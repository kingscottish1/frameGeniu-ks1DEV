from app.config.ollama_models import DEFAULT_OLLAMA_MODEL
from app.config.settings import get_settings
from app.providers.llm.anthropic import AnthropicLLM
from app.providers.llm.base import BaseLLM, DemoLLM
from app.providers.llm.deepseek import DeepSeekLLM
from app.providers.llm.google import GoogleLLM
from app.providers.llm.moonshot import MoonshotLLM
from app.providers.llm.ollama import OllamaLLM
from app.providers.llm.openai import OpenAILLM
from app.providers.llm.qwen import QwenLLM
from app.utils.exceptions import ProviderError


def create_llm(provider: str | None = None) -> BaseLLM:
    settings = get_settings()
    name = (provider or settings.llm_provider or "auto").lower()
    cfg = settings.llm
    timeout = float(cfg.get("timeout_seconds") or 300)
    if name in {"demo", "local", "none", "offline", "studio"}:
        return DemoLLM()
    if name == "openai":
        return OpenAILLM(
            api_key=str(cfg.get("openai_api_key") or ""),
            model=str(cfg.get("openai_model") or "gpt-4o-mini"),
            base_url=str(cfg.get("openai_base_url") or "") or None,
            timeout=timeout,
        )
    if name == "anthropic":
        return AnthropicLLM(
            api_key=str(cfg.get("anthropic_api_key") or ""),
            model=str(cfg.get("anthropic_model") or "claude-3-5-sonnet-latest"),
            timeout=timeout,
        )
    if name in {"google", "gemini"}:
        return GoogleLLM(
            api_key=str(cfg.get("google_api_key") or ""),
            model=str(cfg.get("google_model") or "gemini-2.0-flash"),
        )
    if name == "deepseek":
        return DeepSeekLLM(
            api_key=str(cfg.get("deepseek_api_key") or ""),
            model=str(cfg.get("deepseek_model") or "deepseek-chat"),
            base_url=str(cfg.get("deepseek_base_url") or "https://api.deepseek.com"),
            timeout=timeout,
        )
    if name in {"auto", "local-first"}:
        ollama = OllamaLLM(
            base_url=str(cfg.get("ollama_base_url") or "http://127.0.0.1:11434"),
            model=str(cfg.get("ollama_model") or DEFAULT_OLLAMA_MODEL),
            timeout=max(timeout, 600),
        )
        if ollama.ping() and ollama.list_models():
            ollama.model = ollama.pick_model(str(cfg.get("ollama_model") or DEFAULT_OLLAMA_MODEL))
            return ollama
        return DemoLLM()
    if name == "ollama":
        ollama = OllamaLLM(
            base_url=str(cfg.get("ollama_base_url") or "http://127.0.0.1:11434"),
            model=str(cfg.get("ollama_model") or DEFAULT_OLLAMA_MODEL),
            timeout=max(timeout, 600),
        )
        ollama.model = ollama.pick_model(str(cfg.get("ollama_model") or DEFAULT_OLLAMA_MODEL))
        return ollama
    if name in {"moonshot", "kimi"}:
        return MoonshotLLM(
            api_key=str(cfg.get("moonshot_api_key") or ""),
            model=str(cfg.get("moonshot_model") or "moonshot-v1-8k"),
            base_url=str(cfg.get("moonshot_base_url") or "https://api.moonshot.cn/v1"),
            timeout=timeout,
        )
    if name == "qwen":
        return QwenLLM(
            api_key=str(cfg.get("qwen_api_key") or ""),
            model=str(cfg.get("qwen_model") or "qwen-plus"),
            base_url=str(cfg.get("qwen_base_url") or "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            timeout=timeout,
        )
    raise ProviderError(f"Unknown LLM provider: {name}", stage="llm")


__all__ = ["BaseLLM", "DemoLLM", "create_llm"]
