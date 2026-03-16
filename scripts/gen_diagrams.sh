#!/usr/bin/env bash
# Generate class diagrams from source using pyreverse (bundled with pylint).
# Output: docs/classes.mmd and docs/packages.mmd (Mermaid format)
#
# Usage: bash scripts/gen_diagrams.sh
# Requires: uv sync (dev group includes pylint/pyreverse)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DOCS="$ROOT/docs"

cd "$ROOT"

mkdir -p "$DOCS"

echo "→ Running pyreverse on api/ ..."
uv run pyreverse api/ \
    --output mmd \
    --output-directory "$DOCS" \
    --project broker-accelerator \
    --ignore __pycache__

echo "→ Diagrams written to docs/"
ls -lh "$DOCS"/*.mmd 2>/dev/null || echo "  (no .mmd files — check pylint version supports mmd output)"

echo ""
echo "Tip: paste the contents of docs/classes.mmd into https://mermaid.live to preview."
