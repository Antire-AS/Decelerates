"""add signed_at and signed_by to sla_agreements

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-03-24 00:02:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6g7h8i9"
down_revision: str | None = "c3d4e5f6g7h8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sla_agreements",
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "sla_agreements",
        sa.Column("signed_by", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sla_agreements", "signed_at")
    op.drop_column("sla_agreements", "signed_by")
