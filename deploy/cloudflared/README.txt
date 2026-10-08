Named Cloudflare tunnel
=======================

Quick public URL (no account, random trycloudflare.com link):
  From the FrameGenius folder run tools\CLOUDFLARE.bat
  or:  docker compose --profile tunnel up --build

Custom domain (Cloudflare account required):
  1. Install cloudflared
  2. cloudflared tunnel login
  3. cloudflared tunnel create framegenius
  4. Copy the generated JSON into this folder as credentials.json
  5. Put the tunnel UUID in config.yml and set your hostname
  6. cloudflared tunnel route dns framegenius studio.example.com
  7. docker compose -f docker-compose.yml -f deploy/docker-compose.cloudflare.yml up -d
