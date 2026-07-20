#!/usr/bin/env bash
# One-command run: starts the API (seeding itself from checked-in fixtures)
# and the web dev server. Fresh clone -> `./run.sh` -> dashboard at
# http://localhost:5173.
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

if [ ! -d "$ROOT/.venv" ]; then
  echo "Creating Python virtual environment..."
  python -m venv "$ROOT/.venv"
fi
if [ -f "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="$ROOT/.venv/Scripts/python.exe"
fi

echo "Installing API dependencies..."
"$PY" -m pip install -q -r "$ROOT/api/requirements.txt"

echo "Starting API on http://localhost:8000 ..."
(cd "$ROOT/api" && "$PY" -m uvicorn app.main:app --port 8000) &
API_PID=$!

if [ ! -d "$ROOT/web/node_modules" ]; then
  echo "Installing web dependencies..."
  (cd "$ROOT/web" && npm install)
fi

echo "Starting web dev server on http://localhost:5173 ..."
(cd "$ROOT/web" && npm run dev -- --port 5173) &
WEB_PID=$!

echo ""
echo "LedgerHawk is running:"
echo "  API   http://localhost:8000/api/health"
echo "  Web   http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop both servers."

trap 'kill $API_PID $WEB_PID 2>/dev/null' EXIT INT TERM
wait
