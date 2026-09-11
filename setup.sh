#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "→ venv..."
python -m venv .venv
PY=".venv/bin/python"; [ -x "$PY" ] || PY=".venv/Scripts/python"
"$PY" -m pip install -U pip
"$PY" -m pip install -U -r requirements.txt
"$PY" -m pip freeze > requirements.lock.txt

[ -f .env ] || { cp .env.example .env; echo "→ .env creado"; }

echo
echo "Listo. Ejemplo:"
echo "  $PY -m src --service-domain \"Current Account\" --directorio ./salida/demo -v"
