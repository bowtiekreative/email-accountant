#!/usr/bin/env bash
# Start both the API and the web UI for local-only use.
# Backend → http://localhost:8000   UI → http://localhost:3000
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load backend env if present.
if [ -f "$HERE/backend/.env" ]; then
  set -a; . "$HERE/backend/.env"; set +a
fi

echo "▶ Starting backend (FastAPI) on :8000"
(cd "$HERE/backend" && python -m uvicorn app.main:app --port 8000 --reload) &
BACK_PID=$!

cleanup() { kill "$BACK_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

echo "▶ Starting frontend (Next.js) on :3000"
(cd "$HERE/frontend" && npm run dev)
