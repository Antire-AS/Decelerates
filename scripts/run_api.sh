#!/usr/bin/env bash
# scripts/run_api.sh — start the FastAPI backend on port 8000

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Load .env so DATABASE_URL and API keys are available to the process
set -a; [ -f .env ] && source .env; set +a

exec uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
