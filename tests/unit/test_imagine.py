from pathlib import Path

from app.services.imagine import (
    _is_real_image,
    _stamp_lettering,
    extract_lettering,
    photoreal_prompt,
    visual_prompt_from_message,
    wants_lettering,
)


def test_photoreal_prompt_forbids_text():
    out = photoreal_prompt("draw Danile Kinhian's intense face")
    low = out.lower()
    assert "danile" in low or "kinhian" in low
    assert "no text" in low
    assert "photoreal" in low
    assert "draw" not in low.split(",")[0]


def test_visual_prompt_strips_draw():
    assert "los angeles" in visual_prompt_from_message("Draw a 1947 Los Angeles street").lower()


def test_user_paint_prompt_keeps_what_they_asked():
    from app.services.imagine import user_paint_prompt

    out = user_paint_prompt("draw me a red fox in snow, oil painting, no humans")
    low = out.lower()
    assert "red fox" in low
    assert "snow" in low
    assert "oil painting" in low
    assert "draw me" not in low
    assert user_paint_prompt("a picture") == ""
    assert "castle" in user_paint_prompt("make a picture of a castle at dusk, anime").lower()
    assert "anime" in user_paint_prompt("make a picture of a castle at dusk, anime").lower()


def test_raw_image_prompt_is_not_forced_photoreal():
    from app.services.imagine import image_prompt

    out = image_prompt("Generate an anime girl in a red jacket, neon alley")
    low = out.lower()
    assert "anime" in low
    assert "no text" not in low
    assert "photoreal" not in low


def test_lettering_is_opt_in():
    assert wants_lettering("paint a rainy street") is False
    assert wants_lettering("the historical context of liverpool") is False
    assert wants_lettering('paint a street with the words "Sub and follow."') is True
    assert extract_lettering('paint a street with the words "Sub and follow."').startswith("Sub and follow")
    allow = photoreal_prompt("a street with a title", allow_text=True)
    assert "include the requested text" in allow.lower()
    assert allow.lower().count("no text") == 0


def test_stamp_lettering(tmp_path: Path):
    from PIL import Image

    dest = tmp_path / "card.jpg"
    Image.new("RGB", (640, 360), (20, 20, 24)).save(dest, "JPEG")
    _stamp_lettering(dest, "Sub and follow.")
    assert dest.stat().st_size > 2000


def test_rejects_html_as_image():
    assert _is_real_image(b"<html>nope", 20000) is False
    assert _is_real_image(b'{"error":1}', 20000) is False
    assert _is_real_image(b"\xff\xd8\xff\xe0" + b"\x00" * 8, 400) is False
    assert _is_real_image(b"\xff\xd8\xff\xe0" + b"\x00" * 8, 12000) is True


def test_crown_does_not_treat_topic_as_a_picture():
    from app.services.agent_chat import _wants_pictures, _wants_many

    assert _wants_pictures("tell me about this topic") is False
    assert _wants_pictures("imagine that happened") is False
    assert _wants_pictures("draw me a picture of a ship") is True
    assert _wants_pictures("make 4 pics") is True
    assert _wants_many("tell me something about it") is False
    assert _wants_many("make several pictures") is True


def test_generate_image_does_not_mention_poster_fallback():
    import inspect
    from app.services import imagine

    src = inspect.getsource(imagine)
    assert "render_still" not in src
    assert "poster" not in src.lower() or "no poster" in src.lower()
    assert "image.pollinations.ai" in src
    assert "gen.pollinations.ai" not in src
    assert "private=true" not in src
    assert "_GAP = 16.0" in src
