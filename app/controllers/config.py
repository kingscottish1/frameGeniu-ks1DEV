"""Configuration endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config.defaults import DEFAULT_VOICES, LLM_PROVIDERS, MEDIA_PROVIDERS, TTS_PROVIDERS
from app.config.ollama_models import STUDIO_MODELS
from app.config.settings import get_settings, save_settings
from app.models.config import ConfigUpdate
from app.security.auth import AuthUser, require_auth
from app.security.db import get_db

router = APIRouter(prefix="/config", tags=["config"])


@router.get("")
def read_config(user: AuthUser = Depends(require_auth)) -> dict:
    return get_settings().public_dict()


@router.put("")
def write_config(body: ConfigUpdate, user: AuthUser = Depends(require_auth)) -> dict:
    save_settings(body.sections())
    get_db().audit("config_update", user=user.username)
    return get_settings().public_dict()


@router.get("/options")
def options(user: AuthUser = Depends(require_auth)) -> dict:
    settings = get_settings()
    ollama_models: list[str] = []
    ollama_online = False
    try:
        from app.providers.llm.ollama import OllamaLLM

        client = OllamaLLM(base_url=str(settings.llm.get("ollama_base_url") or "http://127.0.0.1:11434"))
        ollama_online = client.ping()
        pulled = client.list_models()
        # Studio roster first (the models they asked to list), then anything else they pulled.
        seen: set[str] = set()
        ollama_models = []
        pulled_l = {m.lower(): m for m in pulled}
        for prefer in STUDIO_MODELS:
            hit = pulled_l.get(prefer.lower())
            if hit and hit not in seen:
                ollama_models.append(hit)
                seen.add(hit)
                continue
            stem = prefer.split(":")[0].lower()
            for name in pulled:
                if name.split(":")[0].lower() == stem and name not in seen:
                    ollama_models.append(name)
                    seen.add(name)
                    break
        for name in pulled:
            if name not in seen:
                ollama_models.append(name)
                seen.add(name)
    except Exception:
        pass
    return {
        "llm_providers": LLM_PROVIDERS,
        "tts_providers": TTS_PROVIDERS,
        "media_providers": MEDIA_PROVIDERS,
        "voices": DEFAULT_VOICES,
        "templates": ["motivational", "educational", "entertainment", "product", "story", "news", "crime", "true-crime"],
        "aspects": ["9:16", "16:9", "1:1", "4:5", "21:9"],
        "ollama_online": ollama_online,
        "ollama_models": ollama_models,
        "ollama_model": str(settings.llm.get("ollama_model") or ""),
        "suggested_models": STUDIO_MODELS,
        "durations": [
            {"id": 30, "label": "30s"},
            {"id": 60, "label": "1 min"},
            {"id": 300, "label": "5 min"},
            {"id": 600, "label": "10 min"},
            {"id": 900, "label": "15 min"},
            {"id": 1800, "label": "30 min"},
        ],
    }
