# FrameGenius API

Base URL: `http://127.0.0.1:8080`

Interactive docs: `/docs`

## Health

`GET /api/v1/health`

## Create a video

`POST /api/v1/videos`

```json
{
  "topic": "Why deep work feels impossible",
  "template": "motivational",
  "aspect_ratio": "9:16",
  "duration": 30,
  "voice": "en-US-JennyNeural",
  "subtitle_enabled": true,
  "bgm_enabled": true
}
```

Returns a task object with `task_id`.

## Task status

`GET /api/v1/tasks/{task_id}`  
`GET /api/v1/tasks`  
`GET /api/v1/tasks/{task_id}/events` (SSE)  
`POST /api/v1/tasks/{task_id}/cancel`  
`DELETE /api/v1/tasks/{task_id}`

## Download

`GET /api/v1/videos/{task_id}/download`  
`GET /api/v1/videos/{task_id}/thumbnail`

## Config

`GET /api/v1/config`  
`PUT /api/v1/config`  
`GET /api/v1/config/options`

## Publish

`POST /api/v1/upload`

```json
{
  "video_path": "outputs/videos/abc.mp4",
  "title": "Deep work",
  "platforms": ["youtube", "tiktok"]
}
```

Without an Upload-Post key this returns a local receipt so you can publish by hand.
