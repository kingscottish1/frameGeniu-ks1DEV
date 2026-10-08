"""Generate from a hand-written script."""

from app.models.video import VideoParams
from app.services.task import run_sync

SCRIPT = """
Nobody is coming to save your calendar.
Block ninety minutes.
Put the phone in another room.
Do the work that actually moves the number.
"""


def main() -> None:
    params = VideoParams(
        topic="Deep work block",
        script_text=SCRIPT,
        template="story",
        duration=20,
    )
    print(run_sync(params).result)


if __name__ == "__main__":
    main()
