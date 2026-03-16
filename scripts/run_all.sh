#!/usr/bin/env bash
# scripts/run_all.sh — start API + UI in parallel
# Press Ctrl+C to stop both.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

cleanup() {
    echo ""
    echo "Stopping API and UI..."
    kill "$API_PID" "$UI_PID" 2>/dev/null || true
    wait "$API_PID" "$UI_PID" 2>/dev/null || true
    echo "Stopped."
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
