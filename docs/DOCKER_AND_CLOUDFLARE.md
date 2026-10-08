# Docker + Cloudflare — FrameGenius

Author: kingscottishDEV N.A.S

## Easiest: no Docker

Double-click `GO.bat`. Studio: http://127.0.0.1:8080

To put it on the internet for a friend, double-click `tools\CLOUDFLARE.bat` while the studio is running. A `https://….trycloudflare.com` link prints in that window.

## Docker on this PC

Need [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bat
tools\DOCKER.bat
```

or from the FrameGenius folder:

```bat
docker compose up --build
```

Open http://127.0.0.1:8080

Ollama stays on Windows. The container talks to it at `host.docker.internal:11434`.

Renders land in `outputs\videos\` on your desktop copy — download them from Library or that folder.

## Docker + public URL

```bat
docker compose --profile tunnel up --build
```

Watch the `framegenius-tunnel` logs for the trycloudflare link.

## Named tunnel (your own domain)

See `deploy/cloudflared/README.txt`.

```bat
docker compose -f docker-compose.yml -f deploy/docker-compose.cloudflare.yml up -d
```

Set `FRAMEGENIUS_PUBLIC_ORIGIN=https://studio.example.com` in `.env` if you turn auth back on later (`FRAMEGENIUS_AUTH=1`).
