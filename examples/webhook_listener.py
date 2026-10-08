"""Tiny webhook sink for FrameGenius completion events."""

from fastapi import FastAPI, Request
import uvicorn

app = FastAPI(title="FrameGenius webhook sink")


@app.post("/hook")
async def hook(request: Request) -> dict:
    payload = await request.json()
    print("event", payload.get("state"), payload.get("task_id"))
    return {"ok": True}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9099)
