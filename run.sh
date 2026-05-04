#!/usr/bin/env bash
set -euo pipefail

if [ ! -d ".venv" ]; then
  uv venv .venv
fi

uv pip install -r requirements.txt
uv run uvicorn app.main:app --reload
