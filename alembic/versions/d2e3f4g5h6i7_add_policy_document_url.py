"""add document_url to policies

Revision ID: d2e3f4g5h6i7
Revises: c2d3e4f5g6h7
Create Date: 2026-03-23 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d2e3f4g5h6i7"
down_revision: str | None = "c2d3e4f5g6h7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("policies", sa.Column("document_url", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("policies", "document_url")
