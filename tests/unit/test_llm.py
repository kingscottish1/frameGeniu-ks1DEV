from app.providers.llm.base import DemoLLM
from app.services.script import generate_script


def test_demo_llm_returns_text():
    text = DemoLLM().generate("hello")
    assert "FrameGenius" in text or text


def test_demo_script_has_scenes():
    script = generate_script("cold plunges", provider="demo", template="educational", duration=24)
    assert script.title
    assert len(script.scenes) >= 4
    assert script.narration
    assert script.search_terms
