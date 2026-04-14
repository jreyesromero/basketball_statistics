#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VENV="${ROOT}/.venv"
if [[ ! -d "${VENV}" ]]; then
  echo "Creating virtualenv at .venv ..."
  python3 -m venv "${VENV}"
fi

# shellcheck source=/dev/null
source "${VENV}/bin/activate"

echo "Installing dependencies (requirements.txt) ..."
pip install -r "${ROOT}/requirements.txt" -q

if [[ -z "${BASKET_SESSION_SECRET:-}" ]]; then
  export BASKET_SESSION_SECRET="$("${VENV}/bin/python" -c "import secrets; print(secrets.token_hex(32))")"
  echo "Generated ephemeral BASKET_SESSION_SECRET for this run (sign-in cookies reset when the server restarts)."
fi

# On-disk JSON logs (RotatingFileHandler). Override path or set BASKET_LOG_FILE= to disable.
if [[ -z "${BASKET_LOG_FILE+x}" ]]; then
  export BASKET_LOG_FILE="${ROOT}/data/logs/app.jsonl"
fi

echo "Starting app at http://127.0.0.1:8000 (Ctrl+C to stop)"
# Structured JSON request logs from app; disable duplicate Uvicorn access lines.
exec uvicorn src.main:app --reload --host 127.0.0.1 --port 8000 --no-access-log
