#!/usr/bin/env python3
"""Run the full demo seed against the configured DATABASE_URL.

Skips the FastAPI startup path entirely (no migrations, no Alembic, no rate
limiter) so this is fast even against a remote DB. Idempotent — safe to run
repeatedly; existing rows are skipped.

Usage:
    uv run --env-file .env python scripts/seed_demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo_root))

    from api.dependencies import SessionLocal
    from api.services.demo_seed import seed_full_demo

    db = SessionLocal()
    try:
        result = seed_full_demo(db)
    finally:
        db.close()

    print("Seed complete:")
    for k, v in result.items():
        if k != "message":
            print(f"  {k}: {v}")
    print(f"\n{result['message']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
