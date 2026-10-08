"""Queue several topics at once."""

from app.models.video import VideoParams
from app.services.batch import submit_topics
from app.services.task import get_task


def main() -> None:
    base = VideoParams(topic="placeholder", template="motivational", duration=22)
    ids = submit_topics(
        [
            "The myth of overnight success",
            "How to start a writing habit",
            "Cold mornings and clean work",
        ],
        base,
    )
    for task_id in ids:
        print(task_id, get_task(task_id).state if get_task(task_id) else "?")


if __name__ == "__main__":
    main()
