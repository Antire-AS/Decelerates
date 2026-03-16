#!/usr/bin/env bash
# scripts/run_ui.sh — start the Streamlit frontend on port 8501

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

exec uv run streamlit run ui/main.py \
    --server.port=8501 \
    --server.address=0.0.0.0
