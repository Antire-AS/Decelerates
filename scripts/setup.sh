#!/usr/bin/env bash
# scripts/setup.sh — one-time project setup
# Works on macOS, Linux, and Windows WSL

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "==> Checking for uv..."
if ! command -v uv &>/dev/null; then
    echo "    Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
echo "    uv $(uv --version)"

echo "==> Installing dependencies (locked)..."
uv sync --frozen

echo "==> Installing Playwright Chromium..."
uv run playwright install chromium

echo "==> Checking .env file..."
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "    Created .env from .env.example — fill in your API keys"
    else
        echo "    WARNING: no .env or .env.example found"
    fi
else
    echo "    .env already exists"
fi

echo "==> Checking PostgreSQL connection..."
if command -v psql &>/dev/null; then
    DB_URL="${DATABASE_URL:-postgresql://tharusan@localhost:5432/brokerdb}"
    if psql "$DB_URL" -c "SELECT 1" &>/dev/null; then
        echo "    PostgreSQL OK"
    else
        echo "    WARNING: cannot connect to $DB_URL"
        echo "    Make sure PostgreSQL is running and DATABASE_URL is set in .env"
    fi
else
    echo "    psql not found — skipping connection check"
fi

echo ""
echo "Setup complete. Run the project with:"
echo "  bash scripts/run_all.sh"
