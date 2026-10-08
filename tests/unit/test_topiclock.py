from app.services.research import _rank_titles
from app.services.topiclock import (
    football_heavy,
    is_football_topic,
    keep_note,
    keep_page,
    rank_titles,
    strip_off_topic,
    title_is_the_subject,
)


FOOTBALLER = (
    "Darren Bent is an English former footballer who played as a striker. "
    "He made his debut for Ipswich Town and later played in the Premier League "
    "for Charlton Athletic, Tottenham Hotspur and Aston Villa."
)

OAK = (
    "The Money Pit on Oak Island was discovered in 1795. Searchers later found "
    "coconut fibre in the shaft and the pit flooded when diggers reached a wooden platform."
)

GERRARD = (
    "Steven Gerrard is an English former footballer who played as a midfielder. "
    "He spent most of his career at Liverpool F.C. in the Premier League and won the Champions League."
)


def test_football_topic_detection():
    assert is_football_topic("Liverpool F.C.")
    assert is_football_topic("Premier League title race")
    assert not is_football_topic("Oak Island money pit")
    assert not is_football_topic("Darren G Liverpool")


def test_rank_titles_drops_random_footballer():
    titles = [
        "Liverpool F.C.",
        "Darren Bent",
        "Darren Bent (footballer)",
        "Oak Island",
        "Money Pit (Oak Island)",
    ]
    snips = ["", FOOTBALLER, "English footballer", OAK, OAK]
    ranked = rank_titles("Oak Island money pit", titles, snips)
    assert "Oak Island" in ranked
    assert "Darren Bent (footballer)" not in ranked
    assert "Liverpool F.C." not in ranked
    assert "Darren Bent" not in ranked


def test_rank_titles_keeps_the_actual_player():
    titles = ["Steven Gerrard", "Steven Gerrard (footballer)", "Liverpool F.C."]
    ranked = rank_titles("Steven Gerrard", titles)
    assert ranked[0].startswith("Steven Gerrard")


def test_research_rank_wrapper_uses_snippets():
    titles = ["Darren Bent (footballer)", "Oak Island"]
    snips = [FOOTBALLER, OAK]
    ranked = _rank_titles("Oak Island", titles, snips)
    assert ranked[0] == "Oak Island"
    assert "footballer" not in " ".join(ranked).lower()


def test_keep_page_skips_footballer_when_topic_is_not_football():
    assert keep_page(FOOTBALLER, "Oak Island money pit", title="Darren Bent (footballer)") is False
    assert keep_page(OAK, "Oak Island money pit", title="Oak Island") is True
    assert keep_page(GERRARD, "Steven Gerrard", title="Steven Gerrard") is True


def test_keep_note_drops_other_player_keeps_subject():
    assert keep_note(FOOTBALLER, "Oak Island money pit") is False
    assert keep_note(OAK, "Oak Island money pit") is True
    assert keep_note(GERRARD, "Steven Gerrard") is True
    assert keep_note("He grew up in Liverpool and started DJing in local clubs around the docks.", "Darren G Liverpool") is True


def test_strip_off_topic_cuts_the_footballer_pad():
    blob = OAK + "\n\n" + FOOTBALLER
    out = strip_off_topic(blob, "Oak Island money pit")
    assert "Money Pit" in out
    assert "Darren Bent" not in out
    assert "Premier League" not in out


def test_title_is_the_subject():
    assert title_is_the_subject("Steven Gerrard", "Steven Gerrard")
    assert title_is_the_subject("Oak Island", "Oak Island money pit")
    assert not title_is_the_subject("Darren Bent (footballer)", "Darren G Liverpool")


def test_unused_notes_skips_repeats():
    from app.services.topiclock import unused_notes

    notes = (
        "- The Money Pit was discovered in 1795 by three men.\n"
        "- Coconut fibre was found in the shaft years later.\n"
    )
    already = "The Money Pit was discovered in 1795 by three men from the island."
    out = unused_notes(notes, already)
    assert "Coconut fibre" in out
    assert "discovered in 1795" not in out


def test_script_notes_target_is_fat():
    from pathlib import Path

    blob = (Path(__file__).resolve().parents[2] / "app" / "services" / "script.py").read_text(encoding="utf-8")
    assert "return 10000" in blob
    assert "return 12000" in blob
    assert "return 6000" in blob
    assert "duration=dur" in blob or "duration: float = 0.0" in blob


def test_script_module_imports_lock_helpers():
    from pathlib import Path

    blob = (Path(__file__).resolve().parents[2] / "app" / "services" / "script.py").read_text(encoding="utf-8")
    head = blob.split("from app.services.topiclock import", 1)[1].split(")", 1)[0]
    for name in ("allowed_names", "same_story", "lock_narration", "keep_note", "strip_off_topic", "unused_notes"):
        assert name in head, name
    assert "_locked_script" in blob


def test_posh_british_voice_and_human_ssml_are_wired():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    voice = (root / "app" / "services" / "voice.py").read_text(encoding="utf-8")
    edge = (root / "app" / "providers" / "tts" / "edge.py").read_text(encoding="utf-8")
    assert "en-GB-SoniaNeural" in voice
    assert "humanize_ssml" in edge
    assert "break time=" in edge


def test_subject_article_details_are_kept_for_the_writer():
    from app.services.topiclock import keep_note

    assert keep_note(
        "Searchers later found coconut fibre in the shaft.",
        "Oak Island money pit",
    ) is True


def test_random_killer_story_is_not_nicole_blaine():
    from app.services.topiclock import keep_note, keep_page, on_subject, same_story

    topic = "nicole blaine killer"
    other = "A killer in Paris stabbed a chef after a row in a restaurant."
    assert on_subject("Nicole Blaine was arrested in Greenock after the killing.", topic) is True
    assert on_subject(other, topic) is False
    assert keep_note(other, topic) is False
    assert same_story(other, topic) is False
    assert keep_page("The history of French cuisine spans centuries of chefs.", topic, title="French cuisine") is False
    assert keep_page(
        "Nicole Blaine was accused of killing her partner in Greenock.",
        topic,
        title="Nicole Blaine",
    ) is True


def test_lock_narration_drops_random_detours():
    from app.services.topiclock import lock_narration

    blob = (
        "The Money Pit on Oak Island was found in 1795. "
        "Meanwhile a chef in Paris invented a new soup. "
        "Searchers later found coconut fibre in the shaft."
    )
    out = lock_narration(blob, "Oak Island money pit")
    assert "Oak Island" in out or "Money Pit" in out
    assert "Paris" not in out
    assert "chef" not in out


def test_football_heavy_needs_two_markers():
    assert football_heavy("He supported Liverpool as a boy.") is False
    assert football_heavy(FOOTBALLER) is True
