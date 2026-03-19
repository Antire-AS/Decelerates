"""add tags to insurance_documents

Revision ID: fd5ea67956bb
Revises: 4fa17f9b251a
Create Date: 2026-03-19 00:01:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fd5ea67956bb"
down_revision: str | None = "4fa17f9b251a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "insurance_documents",
        sa.Column("tags", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("insurance_documents", "tags")
