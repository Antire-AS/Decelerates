#!/usr/bin/env bash
# scripts/run_all.sh — start Postgres (Docker) + API + UI
# Press Ctrl+C to stop API and UI (Postgres keeps running).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# ── Postgres ──────────────────────────────────────────────────────────────────
echo "==> Ensuring Postgres is running (docker compose)..."
if ! docker compose up postgres -d --wait --remove-orphans; then
    echo ""
    echo "    Failed to start Postgres. Common causes:"
    echo "      - Docker Desktop not running (open it and wait for 'Engine running')"
    echo "      - Port 5432 already in use by another Postgres instance"
    echo "      - docker-compose.yml missing or malformed"
    echo ""
    echo "    Set DATABASE_URL in .env to point to an existing database as an alternative."
    exit 1
fi
echo "    Postgres ready on localhost:5432"
echo ""

# ── Clear stale processes on API/UI ports ─────────────────────────────────────
lsof -ti:8000,8501 | xargs kill -9 2>/dev/null || true

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
