# Batch processing

Create `topics.txt`:

```
Why deep work feels impossible
The myth of overnight success
Cold plunges, minus the nonsense
```

CLI:

```bash
.venv/bin/python cli.py batch topics.txt --template motivational --aspect 9:16
.venv/bin/python cli.py list
```

Python:

```python
from app.models.video import VideoParams
from app.services.batch import submit_topics

ids = submit_topics(
    ["topic one", "topic two"],
    VideoParams(topic="x", template="educational", duration=28),
)
```
