#!/usr/bin/env bash
# Starts the H-MEM memory service and the backend together. Ctrl+C stops both.
#   bash scripts/run_dev.sh
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
[ -f .venv/bin/activate ] && . .venv/bin/activate
PY=$(command -v python || command -v python3)
HMEM_PORT="${HMEM_PORT:-8765}"

if curl -fs "http://127.0.0.1:${HMEM_PORT}/health" >/dev/null 2>&1; then
  echo "[dev] H-MEM service already running on :${HMEM_PORT}"
else
  [ -d engines/hmem/node_modules ] || npm --prefix engines/hmem install --silent
  (cd engines/hmem && exec node --import tsx server.ts) > logs/hmem.log 2>&1 &
  HMEM_PID=$!
  trap 'kill "$HMEM_PID" 2>/dev/null || true' EXIT INT TERM
  for _ in $(seq 1 40); do
    curl -fs "http://127.0.0.1:${HMEM_PORT}/health" >/dev/null 2>&1 && break
    sleep 0.25
  done
  echo "[dev] H-MEM service started (log: logs/hmem.log)"
fi
echo "[dev] starting the backend on http://127.0.0.1:8000  (docs: /docs)"
"$PY" -m uvicorn backend.app.main:app --reload
