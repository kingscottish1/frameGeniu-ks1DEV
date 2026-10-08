from app.config.settings import get_settings
from app.providers.tts.azure import AzureTTS
from app.providers.tts.base import BaseTTS, TTSResult
from app.providers.tts.chatterbox import ChatterboxTTS
from app.providers.tts.edge import EdgeTTS
from app.providers.tts.elevenlabs import ElevenLabsTTS
from app.providers.tts.google import GoogleTTS
from app.providers.tts.siliconflow import SiliconFlowTTS
from app.utils.exceptions import ProviderError


def create_tts(provider: str | None = None) -> BaseTTS:
    settings = get_settings()
    name = (provider or settings.tts_provider or "edge").lower()
    cfg = settings.tts
    if name == "edge":
        return EdgeTTS()
    if name == "azure":
        return AzureTTS(api_key=str(cfg.get("azure_speech_key") or ""), region=str(cfg.get("azure_speech_region") or "eastus"))
    if name == "google":
        return GoogleTTS(api_key=str(cfg.get("google_tts_api_key") or ""))
    if name == "elevenlabs":
        return ElevenLabsTTS(
            api_key=str(cfg.get("elevenlabs_api_key") or ""),
            model=str(cfg.get("elevenlabs_model") or "eleven_multilingual_v2"),
        )
    if name == "siliconflow":
        return SiliconFlowTTS(
            api_key=str(cfg.get("siliconflow_api_key") or ""),
            base_url=str(cfg.get("siliconflow_base_url") or "https://api.siliconflow.cn/v1"),
        )
    if name == "chatterbox":
        return ChatterboxTTS(base_url=str(cfg.get("chatterbox_base_url") or "http://127.0.0.1:8001"))
    raise ProviderError(f"Unknown TTS provider: {name}", stage="tts")


__all__ = ["BaseTTS", "TTSResult", "create_tts"]
