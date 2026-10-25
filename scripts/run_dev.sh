#!/usr/bin/env bash
# Starts the H-MEM memory service and the backend together (and the web UI with WITH_UI=1). Ctrl+C stops everything.
#   bash scripts/run_dev.sh            # memory service + backend
#   WITH_UI=1 bash scripts/run_dev.sh  # ... plus the UI on http://localhost:3001
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
[ -f .venv/bin/activate ] && . .venv/bin/activate
PY=$(command -v python || command -v python3)
HMEM_PORT="${HMEM_PORT:-8765}"
PIDS=()
cleanup() { for p in "${PIDS[@]:-}"; do [ -n "$p" ] && kill "$p" 2>/dev/null || true; done; }
trap cleanup EXIT INT TERM

if curl -fs "http://127.0.0.1:${HMEM_PORT}/health" >/dev/null 2>&1; then
  echo "[dev] H-MEM service already running on :${HMEM_PORT}"
else
  [ -d engines/hmem/node_modules ] || npm --prefix engines/hmem install --silent
  (cd engines/hmem && exec node --import tsx server.ts) > logs/hmem.log 2>&1 &
  PIDS+=("$!")
  for _ in $(seq 1 40); do
    curl -fs "http://127.0.0.1:${HMEM_PORT}/health" >/dev/null 2>&1 && break
    sleep 0.25
  done
  echo "[dev] H-MEM service started (log: logs/hmem.log)"
fi

if [ "${WITH_UI:-0}" = "1" ]; then
  [ -d frontend/node_modules ] || npm --prefix frontend install --silent
  (cd frontend && exec node node_modules/next/dist/bin/next dev -p 3001) > logs/ui.log 2>&1 &
  PIDS+=("$!")
  echo "[dev] UI starting on http://localhost:3001 (log: logs/ui.log)"
fi

echo "[dev] starting the backend on http://127.0.0.1:8000  (docs: /docs)"
"$PY" -m uvicorn backend.app.main:app --reload
