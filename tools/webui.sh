#!/usr/bin/env bash
# FrameGenius WebUI launcher — kingscottishDEV N.A.S
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -x .venv/bin/python ]]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip wheel setuptools
  .venv/bin/pip install -r requirements.txt
fi

if [[ ! -f config.toml ]]; then
  cp config.example.toml config.toml
fi

export PYTHONPATH="${PWD}:${PYTHONPATH:-}"
exec .venv/bin/python -m streamlit run webui/streamlit_app.py \
  --server.address 0.0.0.0 \
  --server.port "${FRAMEGENIUS_WEBUI_PORT:-8501}" \
  --server.headless true \
  --browser.gatherUsageStats false
