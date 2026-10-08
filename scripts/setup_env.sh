#!/usr/bin/env bash
# FrameGenius environment setup — kingscottishDEV N.A.S
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-python3}"
echo "FrameGenius setup using ${PYTHON_BIN}"
${PYTHON_BIN} --version
${PYTHON_BIN} -m venv .venv
.venv/bin/pip install --upgrade pip wheel setuptools
.venv/bin/pip install -r requirements.txt
if [[ ! -f config.toml ]]; then
  cp config.example.toml config.toml
fi
mkdir -p outputs/{videos,scripts,logs,thumbnails,tasks}
echo "Done. Run:  ./webui.sh   or   .venv/bin/python scripts/launch.py --all"
