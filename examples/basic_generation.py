"""Basic FrameGenius generation example — kingscottishDEV N.A.S."""

from app.models.video import AspectRatio, VideoParams
from app.services.task import run_sync


def main() -> None:
    params = VideoParams(
        topic="Why deep work feels impossible in an open office",
        template="educational",
        aspect_ratio=AspectRatio.PORTRAIT,
        duration=24,
        voice="en-US-JennyNeural",
    )
    record = run_sync(params)
    print(record.state, record.result or record.error)


if __name__ == "__main__":
    main()
