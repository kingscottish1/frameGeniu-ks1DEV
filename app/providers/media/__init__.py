from app.config.settings import get_settings
from app.providers.media.base import BaseMediaProvider, MediaClip
from app.providers.media.coverr import CoverrProvider
from app.providers.media.pexels import PexelsProvider
from app.providers.media.pixabay import PixabayProvider
from app.utils.exceptions import ProviderError


def create_media(provider: str | None = None) -> BaseMediaProvider | None:
    settings = get_settings()
    name = (provider or settings.media_provider or "local").lower()
    cfg = settings.media
    timeout = float(cfg.get("download_timeout") or 45)
    if name in {"local", "demo", "none", "offline", "web"}:
        return None
    if name == "pexels":
        return PexelsProvider(api_keys=list(cfg.get("pexels_api_keys") or []), timeout=timeout)
    if name == "pixabay":
        return PixabayProvider(api_keys=list(cfg.get("pixabay_api_keys") or []), timeout=timeout)
    if name == "coverr":
        return CoverrProvider(api_key=str(cfg.get("coverr_api_key") or ""), timeout=timeout)
    raise ProviderError(f"Unknown media provider: {name}", stage="media")


__all__ = ["BaseMediaProvider", "MediaClip", "create_media"]
