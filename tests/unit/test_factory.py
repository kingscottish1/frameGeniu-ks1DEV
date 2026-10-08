from app.models.script import Scene, VideoScript
from app.services.cards import hook_words
from app.services.channel import DEFAULTS, load_channel
from app.services.shorts import plan_windows
from app.services.trends import FALLBACK, fetch_trends


def test_hook_words_caps_and_limits():
    assert hook_words("this is the file on the cartel tonight", 4) == "THIS IS THE FILE"


def test_channel_defaults():
    ch = load_channel()
    assert ch["name"]
    assert "intro_enabled" in ch
    assert "cta_text" in DEFAULTS


def test_shorts_windows_skip_short_films():
    script = VideoScript(title="x", scenes=[Scene(narration="Hi.", duration=5)])
    script.apply_timings()
    assert plan_windows(script, 40) == []


def test_shorts_windows_split_long_film():
    scenes = [Scene(narration=f"Beat {i}.", duration=12) for i in range(10)]
    script = VideoScript(title="long", scenes=scenes)
    script.apply_timings()
    windows = plan_windows(script, script.estimated_duration())
    assert windows
    assert all(b - a >= 22 for a, b in windows)
    assert len(windows) <= 8


def test_trends_fallback_when_web_is_down(monkeypatch):
    from app.services import trends as trends_mod

    def boom(*_a, **_k):
        raise RuntimeError("offline")

    monkeypatch.setattr(trends_mod, "_wikipedia_most", lambda *_a, **_k: [])
    monkeypatch.setattr(trends_mod, "_hacker_news", lambda *_a, **_k: [])
    monkeypatch.setattr(trends_mod, "_duckduckgo", lambda *_a, **_k: [])
    items = fetch_trends("crime", limit=6)
    assert items
    assert all(item.get("title") for item in items)


def test_crime_fallback_exists():
    assert FALLBACK["crime"]
