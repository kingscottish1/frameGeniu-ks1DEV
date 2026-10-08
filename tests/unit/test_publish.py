import inspect

from app.providers.media.coverr import coverr_mp4_url
from app.services.bleep import bleep_audio
from app.services.transcribe import _vosk_words
from app.services.youtube import auth_url


def test_coverr_mp4_url():
    assert coverr_mp4_url("RainOnWindow") == "https://cdn.coverr.co/videos/RainOnWindow/720p.mp4"
    assert coverr_mp4_url("") == ""
    assert coverr_mp4_url("  x/y  ").endswith("/720p.mp4")


def test_youtube_auth_url(monkeypatch):
    from app.services import youtube

    monkeypatch.setattr(youtube, "credentials", lambda: ("abc.apps.googleusercontent.com", "s3cret"))
    url = auth_url("http://127.0.0.1:8080/api/v1/publish/youtube/callback")
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "abc.apps.googleusercontent.com" in url
    assert "youtube.upload" in url
    assert "access_type=offline" in url
    assert "127.0.0.1" in url


def test_vosk_words_parse():
    words = _vosk_words(
        '{"result":[{"word":"hello","start":0.1,"end":0.4},{"word":"world","start":0.4,"end":0.8}]}'
    )
    assert [w.word for w in words] == ["hello", "world"]
    assert words[0].start == 0.1
    assert words[1].end == 0.8
    assert _vosk_words("not json") == []
    assert _vosk_words("{}") == []


def test_still_count_imported_in_stock_media():
    from app.services import stock_media

    assert callable(stock_media.still_count)
    assert stock_media.still_count(30) >= 6
    src = inspect.getsource(stock_media.collect_clips)
    assert "still_count(" in src
    assert "_stock_providers" in src


def test_stock_providers_always_include_coverr():
    class S:
        media = {"pexels_api_keys": ["********"], "pixabay_api_keys": []}

    from app.services.stock_media import _stock_providers

    names = [p.name for p in _stock_providers(S(), 10)]
    assert "coverr" in names
    assert "pexels" not in names


def test_create_media_local_is_none():
    from app.providers.media import create_media

    assert create_media("local") is None


def test_bleep_uses_frame_eval_and_skips_mass_mute():
    src = inspect.getsource(bleep_audio)
    assert "volume=eval=frame" in src
    assert src.count("eval=frame") >= 2
    assert "0.25" in src


def test_sanitize_skips_redacted_secrets():
    from app.config.settings import sanitize_section

    out = sanitize_section(
        {
            "pexels_api_keys": ["********"],
            "youtube_client_secret": "********",
            "youtube_client_id": "abc.apps.googleusercontent.com",
            "provider": "local",
        }
    )
    assert "pexels_api_keys" not in out
    assert "youtube_client_secret" not in out
    assert out["youtube_client_id"] == "abc.apps.googleusercontent.com"
    assert out["provider"] == "local"
