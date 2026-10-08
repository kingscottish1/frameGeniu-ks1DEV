from app.services.video import _grade_filter
from app.utils.validators import aspect_size, safe_filename, validate_aspect


def test_aspect_sizes():
    assert aspect_size("9:16") == (1080, 1920)
    assert aspect_size("16:9") == (1920, 1080)
    assert validate_aspect("1:1") == "1:1"


def test_safe_filename():
    assert "hello" in safe_filename("Hello?? World!!")


def test_grade_filters():
    assert "eq=" in _grade_filter("cinematic")
    assert _grade_filter("none") == ""
