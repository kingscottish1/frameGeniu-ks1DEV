"""Load, cache, and persist FrameGenius configuration."""

from __future__ import annotations

import threading
from copy import deepcopy
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from app.config.defaults import DEFAULT_SYSTEM_PROMPT
from app.utils.env import first_env, load_env
from app.utils.file_manager import FileManager, ROOT, get_ffmpeg
from app.utils.logger import setup_logging

_LOCK = threading.RLock()
_SETTINGS: "Settings | None" = None

SECRET_KEYS = {
    "api_key",
    "openai_api_key",
    "anthropic_api_key",
    "google_api_key",
    "deepseek_api_key",
    "moonshot_api_key",
    "qwen_api_key",
    "azure_speech_key",
    "google_tts_api_key",
    "elevenlabs_api_key",
    "siliconflow_api_key",
    "upload_post_api_key",
    "secret",
    "pexels_api_keys",
    "pixabay_api_keys",
    "coverr_api_key",
    "youtube_client_secret",
    "tiktok_access_token",
}


def _is_placeholder(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, list):
        real = [item for item in value if not _is_placeholder(item)]
        return not real
    text = str(value).strip()
    return text == "" or "****" in text


def sanitize_section(values: dict[str, Any]) -> dict[str, Any]:
    """Drop blank / ******** secrets so a Settings save cannot wipe real keys."""
    out: dict[str, Any] = {}
    for key, value in values.items():
        if isinstance(value, dict):
            nested = sanitize_section(value)
            if nested:
                out[key] = nested
            continue
        if isinstance(value, list):
            cleaned = [item for item in value if not _is_placeholder(item)]
            if key in SECRET_KEYS and not cleaned:
                continue
            out[key] = cleaned
            continue
        if key in SECRET_KEYS and _is_placeholder(value):
            continue
        if isinstance(value, str) and "****" in value:
            continue
        out[key] = value
    return out


def _read_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _dump_toml(data: dict[str, Any], indent: int = 0) -> str:
    """Minimal TOML writer so we do not depend on tomli-w."""
    lines: list[str] = []
    tables: list[tuple[str, dict]] = []
    prefix = "  " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            tables.append((key, value))
            continue
        lines.append(f"{prefix}{key} = {_toml_value(value)}")
    for key, value in tables:
        if lines and lines[-1] != "":
            lines.append("")
        lines.append(f"[{key}]")
        lines.append(_dump_toml(value).rstrip())
    return "\n".join(lines) + "\n"


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    if "\n" in text:
        return '"""' + str(value).replace('"""', '\\"""') + '"""'
    return f'"{text}"'


def _pick(section: dict, key: str, default: Any) -> Any:
    value = section.get(key, default)
    return default if value is None else value


class Settings:
    """Nested dict facade with helpers used across the app."""

    def __init__(self, data: dict[str, Any], path: Path) -> None:
        self.data = data
        self.path = path
        self.root = ROOT
        app = data.setdefault("app", {})
        self.files = FileManager(
            root=self.root,
            output_dir=str(app.get("output_dir", "outputs")),
            resource_dir=str(app.get("resource_dir", "resource")),
        )
        setup_logging(
            self.files.logs,
            debug=bool(app.get("debug", False)),
            hide_log=bool(app.get("hide_log", False)),
        )

    # --- section helpers -------------------------------------------------
    def section(self, name: str) -> dict[str, Any]:
        return self.data.setdefault(name, {})

    def get(self, dotted: str, default: Any = None) -> Any:
        current: Any = self.data
        for part in dotted.split("."):
            if not isinstance(current, dict) or part not in current:
                return default
            current = current[part]
        return current

    def set(self, dotted: str, value: Any) -> None:
        parts = dotted.split(".")
        current = self.data
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value

    def update_section(self, name: str, values: dict[str, Any]) -> None:
        section = self.section(name)
        for key, value in values.items():
            if value is not None:
                section[key] = value

    # --- convenience -----------------------------------------------------
    @property
    def app(self) -> dict[str, Any]:
        return self.section("app")

    @property
    def llm(self) -> dict[str, Any]:
        return self.section("llm")

    @property
    def tts(self) -> dict[str, Any]:
        return self.section("tts")

    @property
    def media(self) -> dict[str, Any]:
        return self.section("media")

    @property
    def video(self) -> dict[str, Any]:
        return self.section("video")

    @property
    def subtitle(self) -> dict[str, Any]:
        return self.section("subtitle")

    @property
    def audio(self) -> dict[str, Any]:
        return self.section("audio")

    @property
    def host(self) -> str:
        return str(self.app.get("host", "0.0.0.0"))

    @property
    def port(self) -> int:
        return int(self.app.get("port", 8080))

    @property
    def webui_port(self) -> int:
        return int(self.app.get("webui_port", 8501))

    @property
    def ffmpeg(self) -> str:
        return get_ffmpeg(str(self.app.get("ffmpeg_path") or "") or None)

    @property
    def llm_provider(self) -> str:
        return str(self.llm.get("provider") or "auto").lower()

    @property
    def tts_provider(self) -> str:
        return str(self.tts.get("provider") or "edge").lower()

    @property
    def media_provider(self) -> str:
        return str(self.media.get("provider") or "local").lower()

    @property
    def system_prompt(self) -> str:
        return str(self.llm.get("system_prompt") or DEFAULT_SYSTEM_PROMPT)

    def proxy(self) -> dict[str, str] | None:
        section = self.section("proxy")
        http = str(section.get("http") or "")
        https = str(section.get("https") or http)
        if not http and not https:
            return None
        return {"http://": http, "https://": https}

    def public_dict(self) -> dict[str, Any]:
        """Config with secrets redacted — safe for the WebUI / API."""
        clone = deepcopy(self.data)
        def redact(node: Any) -> Any:
            if isinstance(node, dict):
                out = {}
                for key, value in node.items():
                    if key in SECRET_KEYS:
                        if isinstance(value, list):
                            out[key] = ["********" if item else "" for item in value]
                        else:
                            out[key] = "********" if value else ""
                    else:
                        out[key] = redact(value)
                return out
            return node

        return redact(clone)

    def save(self) -> None:
        self.path.write_text(_dump_toml(self.data), encoding="utf-8")


def _hydrate_from_env(data: dict[str, Any]) -> dict[str, Any]:
    load_env(ROOT)
    llm = data.setdefault("llm", {})
    tts = data.setdefault("tts", {})
    media = data.setdefault("media", {})
    upload = data.setdefault("upload", {})

    llm["openai_api_key"] = first_env("OPENAI_API_KEY", "FRAMEGENIUS_OPENAI_API_KEY", default=llm.get("openai_api_key", ""))
    llm["anthropic_api_key"] = first_env("ANTHROPIC_API_KEY", default=llm.get("anthropic_api_key", ""))
    llm["google_api_key"] = first_env("GEMINI_API_KEY", "GOOGLE_API_KEY", default=llm.get("google_api_key", ""))
    llm["deepseek_api_key"] = first_env("DEEPSEEK_API_KEY", default=llm.get("deepseek_api_key", ""))
    llm["moonshot_api_key"] = first_env("MOONSHOT_API_KEY", default=llm.get("moonshot_api_key", ""))
    llm["qwen_api_key"] = first_env("QWEN_API_KEY", "DASHSCOPE_API_KEY", default=llm.get("qwen_api_key", ""))
    if first_env("FRAMEGENIUS_LLM_PROVIDER"):
        llm["provider"] = first_env("FRAMEGENIUS_LLM_PROVIDER")
    if first_env("OLLAMA_MODEL", "FRAMEGENIUS_OLLAMA_MODEL"):
        llm["ollama_model"] = first_env("OLLAMA_MODEL", "FRAMEGENIUS_OLLAMA_MODEL")
    if first_env("OLLAMA_HOST", "OLLAMA_BASE_URL"):
        host = first_env("OLLAMA_HOST", "OLLAMA_BASE_URL")
        if host and not host.startswith("http"):
            host = "http://" + host
        llm["ollama_base_url"] = host

    tts["elevenlabs_api_key"] = first_env("ELEVENLABS_API_KEY", default=tts.get("elevenlabs_api_key", ""))
    tts["azure_speech_key"] = first_env("AZURE_SPEECH_KEY", default=tts.get("azure_speech_key", ""))
    tts["azure_speech_region"] = first_env("AZURE_SPEECH_REGION", default=tts.get("azure_speech_region", "eastus"))
    tts["siliconflow_api_key"] = first_env("SILICONFLOW_API_KEY", default=tts.get("siliconflow_api_key", ""))

    pexels = first_env("PEXELS_API_KEY")
    if pexels:
        media["pexels_api_keys"] = [pexels]
        if media.get("provider") in {None, "", "local"}:
            media["provider"] = "pexels"
    pixabay = first_env("PIXABAY_API_KEY")
    if pixabay:
        media["pixabay_api_keys"] = [pixabay]
    coverr = first_env("COVERR_API_KEY")
    if coverr:
        media["coverr_api_key"] = coverr

    upload["upload_post_api_key"] = first_env("UPLOAD_POST_API_KEY", default=upload.get("upload_post_api_key", ""))
    upload["youtube_client_id"] = first_env(
        "YOUTUBE_CLIENT_ID", "FRAMEGENIUS_YOUTUBE_CLIENT_ID", default=upload.get("youtube_client_id", "")
    )
    upload["youtube_client_secret"] = first_env(
        "YOUTUBE_CLIENT_SECRET", "FRAMEGENIUS_YOUTUBE_CLIENT_SECRET", default=upload.get("youtube_client_secret", "")
    )
    return data


def load_settings(path: Path | None = None) -> Settings:
    config_path = Path(path) if path else ROOT / "config.toml"
    if not config_path.exists():
        example = ROOT / "config.example.toml"
        if example.exists():
            config_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            config_path.write_text("[app]\nname = \"FrameGenius\"\n", encoding="utf-8")
    data = _hydrate_from_env(_read_toml(config_path))
    data.setdefault("llm", {}).setdefault("system_prompt", DEFAULT_SYSTEM_PROMPT)
    return Settings(data, config_path)


def get_settings() -> Settings:
    global _SETTINGS
    with _LOCK:
        if _SETTINGS is None:
            _SETTINGS = load_settings()
        return _SETTINGS


def reload_settings() -> Settings:
    global _SETTINGS
    with _LOCK:
        _SETTINGS = load_settings()
        return _SETTINGS


def save_settings(updates: dict[str, Any] | None = None) -> Settings:
    settings = get_settings()
    if updates:
        for section, values in updates.items():
            if isinstance(values, dict):
                settings.update_section(section, values)
    settings.save()
    return reload_settings()
