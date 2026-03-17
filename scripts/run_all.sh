#!/usr/bin/env bash
# scripts/run_all.sh — start Postgres (Docker) + API + UI
# Press Ctrl+C to stop API and UI (Postgres keeps running).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# ── Postgres ──────────────────────────────────────────────────────────────────
echo "==> Ensuring Postgres is running (docker compose)..."
docker compose up postgres -d --wait 2>/dev/null || {
    echo "    Docker not available or postgres failed to start."
    echo "    Make sure Docker Desktop is running, or set DATABASE_URL in .env"
    echo "    to point to an existing database and re-run."
    exit 1
}
echo "    Postgres ready on localhost:5432"
echo ""

cleanup() {
    echo ""
    echo "Stopping API and UI..."
    kill "$API_PID" "$UI_PID" 2>/dev/null || true
    wait "$API_PID" "$UI_PID" 2>/dev/null || true
    echo "Stopped. (Postgres container keeps running — 'docker compose stop postgres' to stop it)"
}
trap cleanup INT TERM

echo "==> Starting API on http://localhost:8000 ..."
bash scripts/run_api.sh &
API_PID=$!

echo "==> Starting UI on http://localhost:8501 ..."
bash scripts/run_ui.sh &
UI_PID=$!

echo ""
echo "Both services running. Open http://localhost:8501 in your browser."
echo "Press Ctrl+C to stop."
echo ""

wait "$API_PID" "$UI_PID"
