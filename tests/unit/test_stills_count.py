from app.services.theme import film_stills, still_count


def test_still_count_scales_with_length():
    assert still_count(30) >= 6
    assert still_count(60) >= 8
    assert still_count(300) >= 20
    assert still_count(1800) <= 48
    assert still_count(300) > still_count(30)


def test_five_minute_film_gets_many_unique_prompts():
    prompts = film_stills("Oak Island money pit", limit=16, duration=300)
    assert len(prompts) >= 12
    assert len(set(prompts)) == len(prompts)
    assert all("oak island" in p.lower() for p in prompts)
    assert "unique take" in prompts[0].lower()
    assert prompts[0] != prompts[1]


def test_short_film_still_gets_enough():
    prompts = film_stills("sourdough starter", duration=30)
    assert len(prompts) >= 6
    assert all("sourdough" in p.lower() for p in prompts)
    other = film_stills("sourdough starter", duration=30, salt="task-aaa")
    third = film_stills("sourdough starter", duration=30, salt="task-bbb")
    assert other != third
