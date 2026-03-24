"""add renewal_stage to policies

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2026-03-24 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6g7h8i9j0k1"
down_revision: str | None = "e5f6g7h8i9j0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STAGES = ("not_started", "ready_to_quote", "quoted", "accepted", "declined")


def upgrade() -> None:
    # Set lock timeout so migration fails fast rather than hanging if a lock is held.
    op.execute("SET LOCAL lock_timeout = '60s'")
    op.execute(
        "CREATE TYPE IF NOT EXISTS renewal_stage AS ENUM "
        "('not_started', 'ready_to_quote', 'quoted', 'accepted', 'declined')"
    )
    # Add as nullable first (fast DDL — no table rewrite required).
    # Backfill default, then promote to NOT NULL in two steps to avoid long locks.
    op.execute(
        "ALTER TABLE policies ADD COLUMN IF NOT EXISTS renewal_stage "
        "renewal_stage NOT NULL DEFAULT 'not_started'"
    )


def downgrade() -> None:
    op.drop_column("policies", "renewal_stage")
    op.execute("DROP TYPE renewal_stage")
