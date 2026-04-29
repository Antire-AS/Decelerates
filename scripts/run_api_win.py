"""
Windows-compatible API runner.

Usage (from project root in PowerShell):
    uv run --env-file .env python scripts/run_api_win.py
"""
import sys
import subprocess
import os

# Run migrations in a separate subprocess (no asyncio interference)
print("Running database migrations...", flush=True)
result = subprocess.run(
    [sys.executable, "-c",
     "from alembic import command as c; from alembic.config import Config; "
     "cfg = Config('alembic.ini'); c.upgrade(cfg, 'head')"],
    env=os.environ.copy(),
)
if result.returncode != 0:
    print("Migrations failed — aborting.", flush=True)
    sys.exit(1)
print("Migrations OK.", flush=True)

# Fix Windows asyncio IocpProactor + psycopg3 blocking hang
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Patch out migration calls in on_startup (already done above)
import api.main as _main
_main._run_migrations_with_lock = lambda cfg: None
_main._stamp_existing_db_if_needed = lambda cfg: None

import uvicorn
uvicorn.run("api.main:app", host="0.0.0.0", port=8000, log_level="info")
