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

echo "Starting app at http://127.0.0.1:8000 (Ctrl+C to stop)"
exec uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
