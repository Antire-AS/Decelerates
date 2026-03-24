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
    op.execute(
        "CREATE TYPE IF NOT EXISTS renewal_stage AS ENUM "
        "('not_started', 'ready_to_quote', 'quoted', 'accepted', 'declined')"
    )
    op.add_column(
        "policies",
        sa.Column(
            "renewal_stage",
            sa.Enum(*_STAGES, name="renewal_stage", create_type=False),
            nullable=False,
            server_default="not_started",
        ),
    )


def downgrade() -> None:
    op.drop_column("policies", "renewal_stage")
    op.execute("DROP TYPE renewal_stage")
