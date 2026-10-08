from app.models.script import Scene, VideoScript
from app.services.hook import punch_hook, shape_script
from app.services.series import series_label
from app.services.theme import detect_theme, shot_prompts


def test_punch_hook_uses_any_topic():
    line = punch_hook("sourdough starter")
    assert "sourdough starter" in line.lower()
    other = punch_hook("orbital shipyard")
    assert "orbital shipyard" in other.lower()


def test_punch_hook_uses_research_fact_not_stock():
    from app.models.research import ResearchBrief

    brief = ResearchBrief(topic="comet", facts=["Halley's comet last appeared in 1986 and will return in 2061."])
    line = punch_hook("Halley's comet", brief)
    assert "1986" in line or "2061" in line or "Halley" in line
    assert "they told you" not in line.lower()


def test_hook_lock_makes_first_scene_short():
    scenes = [Scene(narration="A long rambling opening that goes on and on about nothing useful.", duration=8)]
    script = VideoScript(title="x", scenes=scenes, hook="old")
    script.apply_timings()
    out = shape_script(script, "comet watchers", hook_lock=True)
    assert out.scenes[0].duration <= 3.2
    assert out.hook


def test_series_label_any_name():
    assert series_label("Sourdough Lab", 2, 5) == "Sourdough Lab · Part 2 of 5"


def test_series_shapes_title_and_tease(tmp_path, monkeypatch):
    monkeypatch.setenv("FRAMEGENIUS_DATA_DIR", str(tmp_path))
    scenes = [Scene(narration="Middle beat.", duration=4)]
    script = VideoScript(title="x", scenes=scenes)
    script.apply_timings()
    out = shape_script(
        script,
        "baychimo",
        hook_lock=True,
        series_name="Ghost Ships",
        series_part=1,
        series_total=4,
    )
    assert "Ghost Ships" in out.title
    assert any("next time" in s.narration.lower() for s in out.scenes)


def test_unknown_subject_is_not_forced_crime():
    assert detect_theme("sourdough starter", "auto").id != "crime"
    blob = " ".join(shot_prompts("sourdough starter", "auto")).lower()
    assert "sourdough" in blob
    assert "crime scene tape" not in blob
    assert "sunrise over a mountain" not in blob
