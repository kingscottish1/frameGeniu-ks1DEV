from app.services.script import _is_speakable, generate_script


def test_rejects_scrape_junk():
    from app.services.script import _is_junk, _scrub_speech

    assert _is_junk("'][]['#as al that stuff") is True
    assert _is_junk("#'];' var x = 1") is True
    clean = _scrub_speech("Nicole was arrested. '][]['#as. The trial started in Greenock.")
    assert "Nicole" in clean
    assert "][" not in clean
    assert "#" not in clean
    assert _is_speakable("#'];' var x = 1") is False
    assert _is_speakable("function(){ return true }") is False
    assert _is_speakable("See https://example.com/page for more") is False
    assert _is_speakable("Darren grew up in Liverpool and started DJing in local clubs.") is True


def test_custom_script_splits_sentences():
    script = generate_script(
        "focus",
        custom_script="One. Two. Three is the charm of a longer line.",
        provider="demo",
    )
    assert len(script.scenes) >= 2
    assert "One." in script.narration


def test_templates_exist():
    for name in ("motivational", "educational", "entertainment", "product", "story", "news", "crime"):
        script = generate_script("framegenius", template=name, provider="demo")
        assert script.scenes
        narrations = [scene.narration for scene in script.scenes]
        assert len(narrations) == len(set(narrations))
        assert "Stay with this" not in script.narration


def test_studio_script_does_not_loop():
    script = generate_script("framegenius", template="crime", provider="demo", duration=300)
    assert script.scenes
    assert "Stay with this" not in script.narration
    assert len({scene.narration for scene in script.scenes}) == len(script.scenes)


def test_research_script_does_not_speak_random_footballer():
    from app.models.research import ResearchBrief

    footballer = (
        "Darren Bent is an English former footballer who played as a striker. "
        "He made his debut for Ipswich Town and later played in the Premier League."
    )
    brief = ResearchBrief(
        topic="Oak Island money pit",
        summary="A pit on Oak Island off Nova Scotia.",
        facts=[
            "The Money Pit was discovered in 1795 by three men from the island.",
            footballer,
            "Searchers found coconut fibre in the pit and the shaft later flooded.",
        ],
        extracts=[
            "The Money Pit on Oak Island was discovered in 1795. Searchers later found coconut fibre in the shaft."
        ],
        queries=["Oak Island"],
    )
    script = generate_script(
        "Oak Island money pit",
        template="story",
        provider="studio",
        duration=60,
        research=brief,
    )
    narr = script.narration
    assert "Darren Bent" not in narr
    assert "midfielder" not in narr.lower()
    assert "Premier League" not in narr
    assert "Oak Island" in narr or "pit" in narr.lower() or "Money Pit" in narr


def test_research_script_uses_facts():
    from app.models.research import ResearchBrief

    brief = ResearchBrief(
        topic="Black Dahlia",
        summary="Elizabeth Short was found in Leimert Park in 1947.",
        facts=[
            "Elizabeth Short was 22 years old.",
            "The case remains officially unsolved.",
            "The press named her the Black Dahlia.",
            "The body was discovered in a vacant lot on South Norton Avenue.",
            "The LAPD interviewed hundreds of people and never charged anyone.",
        ],
        extracts=["Detectives followed hundreds of leads and none closed the file."],
        queries=["Black Dahlia", "Leimert Park"],
        image_queries=["Elizabeth Short", "1947 Los Angeles"],
    )
    script = generate_script("Black Dahlia", template="true-crime", provider="studio", duration=60, research=brief)
    assert "Elizabeth" in script.narration or "Dahlia" in script.narration
    assert "Stay with this" not in script.narration
    assert "Hold that against" not in script.narration
    assert len({scene.narration for scene in script.scenes}) == len(script.scenes)
    assert script.scenes
