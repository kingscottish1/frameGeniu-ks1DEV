from pathlib import Path

from app.models.audio import WordTiming
from app.models.script import Scene, VideoScript
from app.services.script import _word_target
from app.services.subtitle import build_subtitles, _from_words


def _script() -> VideoScript:
    return VideoScript(
        title="Darren",
        scenes=[Scene(narration="Darren grew up in Liverpool and started DJing in local clubs.")],
    )


def test_crown_never_names_its_model():
    from app.services.agent_chat import _scrub_identity

    out = _scrub_identity("I am Gemma 26b running on Ollama, 17GB uncensored.")
    low = out.lower()
    assert "gemma" not in low
    assert "ollama" not in low
    assert "17gb" not in low.replace(" ", "")


def test_five_minute_needs_enough_words():
    assert 700 <= _word_target(300) <= 850


def test_thirty_minute_needs_a_full_script():
    from app.services.script import _notes_target

    assert 4000 <= _word_target(1800) <= 5000
    assert 10000 <= _notes_target(1800) <= 11000


def test_captions_do_not_split_on_commas():
    words = [
        WordTiming(word="Hello,", start=0.0, end=0.3),
        WordTiming(word="this", start=0.3, end=0.5),
        WordTiming(word="is", start=0.5, end=0.65),
        WordTiming(word="a", start=0.65, end=0.75),
        WordTiming(word="longer", start=0.75, end=1.1),
        WordTiming(word="spoken", start=1.1, end=1.4),
        WordTiming(word="line", start=1.4, end=1.7),
        WordTiming(word="now.", start=1.7, end=2.1),
        WordTiming(word="Second", start=2.2, end=2.5),
        WordTiming(word="sentence", start=2.5, end=2.9),
        WordTiming(word="holds", start=2.9, end=3.2),
        WordTiming(word="the", start=3.2, end=3.35),
        WordTiming(word="screen", start=3.35, end=3.7),
        WordTiming(word="steady.", start=3.7, end=4.2),
    ]
    cues = _from_words(words, 8)
    assert len(cues) <= 3
    assert not any(c.text == "Hello," for c in cues)


def test_captions_stretch_to_real_voice(tmp_path: Path):
    vocab = "The quick story about Darren in Liverpool keeps moving along now".split()
    tokens = (vocab * 12)[:72]
    words = []
    t = 0.0
    for i, w in enumerate(tokens):
        token = w + ("." if i % 8 == 7 else "")
        words.append(WordTiming(word=token, start=t, end=t + 0.16))
        t += 0.18
    # Word clocks finish around 13s; real voice bed is 40s.
    track = build_subtitles(_script(), words=words, duration=40.0, workdir=tmp_path)
    assert track.cues
    assert track.cues[-1].end >= 38.0
    for cue in track.cues[:-1]:
        assert cue.end - cue.start >= 1.5


def test_pick_model_does_not_confuse_gemma4():
    from app.providers.llm.ollama import OllamaLLM

    client = OllamaLLM()
    installed = [
        "1stageze/gemma4-26b-uncensored-1m:latest",
        "gemma4:latest",
        "gemma4-pro:latest",
        "qwen3.6-pro:latest",
        "qwen-coder-fast:latest",
    ]
    client.list_models = lambda: installed  # type: ignore[method-assign]
    assert client.pick_model("gemma4:latest") == "gemma4:latest"
    assert client.pick_model("gemma4") == "gemma4:latest"
    assert client.pick_model("1stageze/gemma4-26b-uncensored-1m:latest") == "1stageze/gemma4-26b-uncensored-1m:latest"
    assert client.pick_model("qwen3.6-pro:latest") == "qwen3.6-pro:latest"
    assert client.pick_model(None) == "1stageze/gemma4-26b-uncensored-1m:latest"
    from app.config.ollama_models import CROWN_MODEL

    assert CROWN_MODEL == "1stageze/gemma4-26b-uncensored-1m:latest"
    assert client.pick_model(CROWN_MODEL) == "1stageze/gemma4-26b-uncensored-1m:latest"
