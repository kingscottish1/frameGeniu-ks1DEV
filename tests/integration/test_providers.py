from app.providers.llm import create_llm
from app.providers.tts import create_tts


def test_demo_factory():
    llm = create_llm("demo")
    assert llm.name == "demo"


def test_edge_factory():
    tts = create_tts("edge")
    assert tts.name == "edge"
