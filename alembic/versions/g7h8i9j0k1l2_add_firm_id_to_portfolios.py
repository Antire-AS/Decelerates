"""add firm_id to portfolios

Revision ID: g7h8i9j0k1l2
Revises: f6g7h8i9j0k1
Create Date: 2026-03-24 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "g7h8i9j0k1l2"
down_revision: str | None = "f6g7h8i9j0k1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "portfolios",
        sa.Column("firm_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_portfolios_firm_id", "portfolios", ["firm_id"])
    op.create_foreign_key(
        "fk_portfolios_firm_id",
        "portfolios", "broker_firms",
        ["firm_id"], ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_portfolios_firm_id", "portfolios", type_="foreignkey")
    op.drop_index("ix_portfolios_firm_id", table_name="portfolios")
    op.drop_column("portfolios", "firm_id")
