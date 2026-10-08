from app.services.postkit import build_postkit
from app.services.script import generate_script
from app.models.research import ResearchBrief, Source


def test_postkit_writes_files(tmp_path):
    brief = ResearchBrief(
        topic="Oak Island",
        summary="A money pit story off Nova Scotia.",
        sources=[Source(title="Oak Island", url="https://en.wikipedia.org/wiki/Oak_Island", snippet="pit")],
        people=["McGinnis"],
    )
    script = generate_script("Oak Island", provider="studio", template="story", duration=30, research=brief)
    kit = build_postkit(
        topic="Oak Island",
        script=script,
        research=brief,
        track=None,
        duration=30,
        workdir=tmp_path,
        video_name="oak.mp4",
    )
    assert (tmp_path / "POST.md").exists()
    assert kit["titles"]
    assert any("Oak" in tag or "oak" in tag.lower() for tag in kit["hashtags"])
