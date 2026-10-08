# API integration

```python
import time
import httpx

base = "http://127.0.0.1:8080/api/v1"
task = httpx.post(base + "/videos", json={"topic": "Deep work", "duration": 24}).json()
task_id = task["task_id"]
while True:
    state = httpx.get(f"{base}/tasks/{task_id}").json()
    if state["state"] in {"completed", "failed"}:
        break
    time.sleep(2)
print(state)
```

See `examples/api_integration.py` and `examples/webhook_listener.py`.
