from pathlib import Path

from app.models.audio import WordTiming
from app.models.script import VideoScript
from app.services.subtitle import build_subtitles


def test_subtitles_from_script(tmp_path: Path, script: VideoScript):
    track = build_subtitles(script, duration=8, workdir=tmp_path)
    assert track.cues
    assert Path(track.srt_path).exists()
    assert Path(track.ass_path).exists()
    assert "-->" in Path(track.srt_path).read_text(encoding="utf-8")


def test_subtitles_from_words(tmp_path: Path, script: VideoScript):
    words = [
        WordTiming(word="Start", start=0.0, end=0.3),
        WordTiming(word="now.", start=0.3, end=0.7),
        WordTiming(word="Stay", start=0.8, end=1.1),
        WordTiming(word="longer", start=1.1, end=1.5),
    ]
    track = build_subtitles(script, words=words, duration=2, workdir=tmp_path)
    assert track.cues[0].text


def test_render_ass_accepts_theme(tmp_path: Path, script: VideoScript):
    from app.services.theme import detect_theme

    theme = detect_theme("irish kingpin", "motivational")
    assert theme.id == "crime"
    track = build_subtitles(script, duration=8, workdir=tmp_path, theme=theme)
    ass = Path(track.ass_path).read_text(encoding="utf-8")
    assert "Dialogue:" in ass
    # crime font #F4F1EA → ASS &H00EAF1F4
    assert "EAF1F4" in ass.upper()
