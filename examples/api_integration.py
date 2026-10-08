"""Call the FrameGenius REST API."""

import time

import httpx

BASE = "http://127.0.0.1:8080/api/v1"


def main() -> None:
    created = httpx.post(BASE + "/videos", json={"topic": "FrameGenius in 30 seconds", "duration": 20})
    created.raise_for_status()
    task_id = created.json()["task_id"]
    print("task", task_id)
    while True:
        state = httpx.get(f"{BASE}/tasks/{task_id}").json()
        print(state["stage"], state["progress"])
        if state["state"] in {"completed", "failed"}:
            print(state)
            break
        time.sleep(2)


if __name__ == "__main__":
    main()
