#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip wheel setuptools
  .venv/bin/pip install -r requirements.txt
fi
[[ -f .env ]] || cp .env.example .env
[[ -f config.toml ]] || cp config.example.toml config.toml
.venv/bin/python scripts/bootstrap_env.py
.venv/bin/python scripts/set_login.py
exec .venv/bin/python main.py --host 0.0.0.0 --port "${PORT:-8080}"
