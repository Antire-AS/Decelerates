# Pending migrations (not auto-applied)

Files in this folder are **NOT** picked up by `alembic upgrade head`. Only the
files inside `alembic/versions/` get auto-discovered. This folder holds
migrations that are written-but-gated — they ship in the codebase ready to apply
the day a business trigger fires (e.g. onboarding a 2nd broker firm), but they
don't auto-run on every deploy.

## How to activate a pending migration

1. Read the file's docstring for any companion code changes (model / service /
   router updates) that must ship with the migration.
2. Apply those companion code changes manually.
3. Move the file into `alembic/versions/` and update its `down_revision` to
   point to the current head:
   ```bash
   git mv alembic/pending/<file>.py alembic/versions/<file>.py
   uv run alembic current   # → note the current head id
   # edit down_revision in the migration file to match the head id above
   uv run alembic upgrade head --sql > /tmp/preview.sql   # dry-run
   ```
4. Review `/tmp/preview.sql`, then run `uv run alembic upgrade head` for real.
5. Verify with `uv run alembic current` and any companion smoke tests.

## Current pending migrations

| File | Trigger | Owner |
|------|---------|-------|
| `broker_settings_per_firm.py` | Onboarding 2nd broker firm (replaces the 409 fence in `_resolve_single_firm_id`) | plan §🟡 #8 |
