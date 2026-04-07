#!/usr/bin/env bash
# Regenerate frontend TypeScript types from FastAPI's OpenAPI schema.
#
# This is a TWO-step process so the API server doesn't need to be running:
#   1. Dump the schema by importing api.main and calling app.openapi()
#   2. Run openapi-typescript on the dumped JSON
#
# Run from the frontend directory:
#   bash scripts/gen-api-types.sh
#
# Or via npm:
#   npm run gen:api-types
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCHEMA_PATH="$REPO_ROOT/frontend/src/lib/openapi-schema.json"
TYPES_PATH="$REPO_ROOT/frontend/src/lib/api-schema.ts"

echo "==> Dumping OpenAPI schema from FastAPI app..."
(cd "$REPO_ROOT" && uv run python scripts/dump_openapi.py "$SCHEMA_PATH")

echo "==> Generating TypeScript types from schema..."
(cd "$REPO_ROOT/frontend" && npx openapi-typescript "$SCHEMA_PATH" -o "$TYPES_PATH")

echo "Done. Generated $TYPES_PATH"
echo "Import via:  import type { paths, components } from '@/lib/api-schema';"
