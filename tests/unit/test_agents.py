from app.agents.orchestrator import DEFAULT_CREW, Conductor
from app.agents.writer import WriterAgent
from app.models.video import VideoParams


def test_crew_order():
    names = [cls.name for cls in DEFAULT_CREW]
    assert names == [
        "research",
        "writer",
        "text",
        "voice",
        "backgrounds",
        "media",
        "caption",
        "editor",
        "publisher",
    ]


def test_conductor_builds_nine_agents():
    assert len(Conductor().crew) == 9


def test_writer_agent(tmp_path):
    from app.agents.base import AgentContext

    ctx = AgentContext(
        task_id="abc123abc123",
        params=VideoParams(topic="deep work", template="educational", duration=20),
        workdir=tmp_path,
    )
    result = WriterAgent().run(ctx)
    assert result.ok
    assert ctx.payload["script"].scenes
    assert (tmp_path / "script.json").exists()
