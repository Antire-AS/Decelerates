"""add parsed fields to insurance_offers

Revision ID: a2b3c4d5e6f7
Revises: fd5ea67956bb
Create Date: 2026-03-23 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: str | None = "fd5ea67956bb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for col in ("parsed_premie", "parsed_dekning", "parsed_egenandel",
                "parsed_vilkaar", "parsed_styrker", "parsed_svakheter"):
        op.add_column("insurance_offers", sa.Column(col, sa.String(), nullable=True))


def downgrade() -> None:
    for col in ("parsed_premie", "parsed_dekning", "parsed_egenandel",
                "parsed_vilkaar", "parsed_styrker", "parsed_svakheter"):
        op.drop_column("insurance_offers", col)
