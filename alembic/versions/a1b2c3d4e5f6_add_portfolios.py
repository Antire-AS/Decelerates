"""add portfolios and portfolio_companies tables

Revision ID: a1b2c3d4e5f6
Revises: fd5ea67956bb
Create Date: 2026-03-21 20:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "fd5ea67956bb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portfolios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_portfolios_id", "portfolios", ["id"])

    op.create_table(
        "portfolio_companies",
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.Column("orgnr", sa.String(9), nullable=False),
        sa.Column("added_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("portfolio_id", "orgnr"),
    )


def downgrade() -> None:
    op.drop_table("portfolio_companies")
    op.drop_index("ix_portfolios_id", table_name="portfolios")
    op.drop_table("portfolios")
