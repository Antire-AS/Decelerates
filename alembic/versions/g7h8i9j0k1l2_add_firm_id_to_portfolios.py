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
    op.execute("SET LOCAL lock_timeout = '60s'")
    op.execute(
        "ALTER TABLE portfolios ADD COLUMN IF NOT EXISTS firm_id INTEGER"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_portfolios_firm_id ON portfolios (firm_id)"
    )
    op.execute(
        "ALTER TABLE portfolios DROP CONSTRAINT IF EXISTS fk_portfolios_firm_id"
    )
    op.execute(
        "ALTER TABLE portfolios ADD CONSTRAINT fk_portfolios_firm_id "
        "FOREIGN KEY (firm_id) REFERENCES broker_firms(id) ON DELETE CASCADE"
    )


def downgrade() -> None:
    op.drop_constraint("fk_portfolios_firm_id", "portfolios", type_="foreignkey")
    op.drop_index("ix_portfolios_firm_id", table_name="portfolios")
    op.drop_column("portfolios", "firm_id")
