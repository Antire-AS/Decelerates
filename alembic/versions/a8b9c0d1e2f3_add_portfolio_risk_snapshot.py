"""add portfolio_risk_snapshot table

Revision ID: a8b9c0d1e2f3
Revises: h4i5j6k7l8m9
Create Date: 2026-04-22 20:40:00.000000

Stores per-company Altman Z'' snapshots scoped to a portfolio so the
portfolio-risk dashboard can (a) show zone distribution at a glance and
(b) compute zone transitions by diffing the latest snapshot against the
previous one. Does not replace the point-in-time Altman on company
profiles — that still computes fresh from company_history/regnskap_raw.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a8b9c0d1e2f3"
down_revision: str | None = "h4i5j6k7l8m9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portfolio_risk_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.Column("orgnr", sa.String(length=9), nullable=False),
        sa.Column("z_score", sa.Float(), nullable=True),
        sa.Column("zone", sa.String(length=16), nullable=True),
        sa.Column("score_20", sa.Integer(), nullable=True),
        sa.Column(
            "snapshot_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_portfolio_risk_snapshot_portfolio_snapshot",
        "portfolio_risk_snapshot",
        ["portfolio_id", sa.text("snapshot_at DESC")],
    )
    op.create_index(
        "ix_portfolio_risk_snapshot_portfolio_orgnr_snapshot",
        "portfolio_risk_snapshot",
        ["portfolio_id", "orgnr", sa.text("snapshot_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_portfolio_risk_snapshot_portfolio_orgnr_snapshot",
        table_name="portfolio_risk_snapshot",
    )
    op.drop_index(
        "ix_portfolio_risk_snapshot_portfolio_snapshot",
        table_name="portfolio_risk_snapshot",
    )
    op.drop_table("portfolio_risk_snapshot")
