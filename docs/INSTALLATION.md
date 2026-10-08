# Installation

## Windows (easiest)

1. Install [Python 3.11+](https://www.python.org/downloads/) and tick **Add python.exe to PATH**.
2. Double-click `INSTALL.bat`.
3. Double-click `START.bat`.
4. The studio opens at http://127.0.0.1:8501

Aliases: `easy_install.bat`, `easy_start.bat`.

## macOS / Linux

```bash
chmod +x scripts/setup_env.sh webui.sh
./scripts/setup_env.sh
./webui.sh
```

Or:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.toml config.toml
python scripts/launch.py --all
```

## Docker

```bash
docker compose up --build
```

GPU:

```bash
docker compose -f docker-compose.gpu.yml up --build
```

## FFmpeg

`imageio-ffmpeg` ships a binary. A system install is optional.

```bash
./scripts/install_ffmpeg.sh
```

## First-run note

Demo mode is on. You can render a video with **no API keys**.
Add Pexels + an LLM key in **Settings** when you want better writing and live stock footage.
