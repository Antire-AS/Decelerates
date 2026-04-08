#!/usr/bin/env python3
"""Dump the FastAPI OpenAPI schema to a JSON file.

Used by `frontend/scripts/gen-api-types.sh` to feed openapi-typescript without
requiring the API server to be running. Run from the repo root:

    uv run python scripts/dump_openapi.py [output_path]

Default output: frontend/src/lib/openapi-schema.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo_root))

    # Importing api.main wires up the FastAPI app and all routers
    from api.main import app  # noqa: E402

    out_path = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else repo_root / "frontend" / "src" / "lib" / "openapi-schema.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    schema = app.openapi()
    out_path.write_text(json.dumps(schema, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote OpenAPI schema → {out_path} ({len(schema.get('paths', {}))} paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
