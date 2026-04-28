"""add property_metadata JSONB to companies (file recovery)

Revision ID: o3p4q5r6s7t8
Revises: n2o3p4q5r6s7
Create Date: 2026-04-28 12:38:00.000000

The migration file shipped with PR #267 was somehow dropped from the
commit (only the model + routes + schemas + tests landed; the alembic
file did not). The schema change `companies.property_metadata` is
referenced by the model on main but no migration tracks it. Result:
- prod DB likely has the column already (from one of the doomed
  earlier deploys that ran the migration before crashing) — but the
  alembic_version in the prod DB still records `n2o3p4q5r6s7`
- staging / fresh DBs would not have the column

The `IF NOT EXISTS` in this migration makes it safe in both cases:
- prod: ADD COLUMN is a no-op (column already there); alembic_version
  advances to o3p4q5r6s7t8
- fresh: column gets added cleanly

Same safety patterns from feedback_deploy_migration_safety.md:
- IF NOT EXISTS — idempotent
- lock_timeout 5s — bail out on contention
- statement_timeout 15s — second-line guard
"""

from collections.abc import Sequence

from alembic import op


revision: str = "o3p4q5r6s7t8"
down_revision: str | None = "n2o3p4q5r6s7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("SET LOCAL statement_timeout = '15s'")
    op.execute("ALTER TABLE companies ADD COLUMN IF NOT EXISTS property_metadata JSONB")


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("SET LOCAL statement_timeout = '15s'")
    op.execute("ALTER TABLE companies DROP COLUMN IF EXISTS property_metadata")
