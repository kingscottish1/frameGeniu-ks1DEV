#!/usr/bin/env bash
# Best-effort FFmpeg installer. FrameGenius also ships imageio-ffmpeg.
set -euo pipefail
if command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg already on PATH: $(command -v ffmpeg)"
  ffmpeg -version | head -n 1
  exit 0
fi
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update && sudo apt-get install -y ffmpeg
elif command -v brew >/dev/null 2>&1; then
  brew install ffmpeg
elif command -v dnf >/dev/null 2>&1; then
  sudo dnf install -y ffmpeg
else
  echo "Install ffmpeg from https://ffmpeg.org/download.html"
  echo "FrameGenius will fall back to the bundled imageio-ffmpeg binary."
  exit 0
fi
ffmpeg -version | head -n 1
