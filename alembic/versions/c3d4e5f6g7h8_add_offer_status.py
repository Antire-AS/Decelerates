"""add offer_status to insurance_offers

Revision ID: c3d4e5f6g7h8
Revises: b3c4d5e6f7g8
Create Date: 2026-03-24 00:01:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6g7h8"
down_revision: str | None = "b3c4d5e6f7g8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE offer_status AS ENUM ('pending', 'accepted', 'rejected', 'negotiating')"
    )
    op.add_column(
        "insurance_offers",
        sa.Column(
            "status",
            sa.Enum("pending", "accepted", "rejected", "negotiating", name="offer_status"),
            nullable=True,
            server_default="pending",
        ),
    )


def downgrade() -> None:
    op.drop_column("insurance_offers", "status")
    op.execute("DROP TYPE offer_status")
