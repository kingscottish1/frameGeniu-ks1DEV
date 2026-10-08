from app.models.audio import WordTiming
from app.services.bleep import is_profane, profane_ranges


def test_flags_swears_not_class():
    assert is_profane("fucking") is True
    assert is_profane("Shit!") is True
    assert is_profane("class") is False
    assert is_profane("assess") is False
    assert is_profane("scrap") is False
    assert is_profane("cocktail") is False


def test_merges_close_hits():
    words = [
        WordTiming(word="hello", start=0.0, end=0.4),
        WordTiming(word="fuck", start=1.0, end=1.3),
        WordTiming(word="you", start=1.35, end=1.5),
        WordTiming(word="ok", start=4.0, end=4.2),
    ]
    hits = profane_ranges(words)
    assert hits
    assert hits[0][0] < 1.0
    assert hits[0][1] > 1.3
