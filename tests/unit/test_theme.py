from app.services.theme import detect_theme, shot_prompts


def test_crime_theme_from_topic():
    theme = detect_theme("Black Dahlia murder case", "auto")
    assert theme.id == "crime"
    assert "police" in " ".join(theme.shots).lower() or "crime" in " ".join(theme.shots).lower()


def test_gym_theme_from_topic():
    theme = detect_theme("5am gym deadlift routine", "")
    assert theme.id == "gym"


def test_shots_include_topic():
    shots = shot_prompts("Black Dahlia", "true-crime")
    assert shots
    assert all("dahlia" in s.lower() for s in shots)
    assert all("no children" in s.lower() or "no kids" in s.lower() for s in shots)


def test_kingpin_topic_is_crime_on_auto():
    theme = detect_theme("irish kingpin", "auto")
    assert theme.id == "crime"
    blob = " ".join(shot_prompts("irish kingpin", "auto")).lower()
    assert "kingpin" in blob
    assert "sunrise over a mountain" not in blob


def test_any_subject_gets_topic_shots_not_stock_sunrise():
    shots = " ".join(shot_prompts("sourdough starter", "auto")).lower()
    assert "sourdough" in shots
    assert "sunrise over a mountain" not in shots
    assert "crime scene tape" not in shots
