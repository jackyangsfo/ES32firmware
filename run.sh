#!/bin/bash
# Always launch the GUI with the project virtualenv.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Missing $PY"
  echo "Create it with: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi
exec "$PY" "$ROOT/es32fw.py" "$@"
