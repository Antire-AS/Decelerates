"""Add last_refreshed_at to companies.

Tracks when the risk monitor agent last fetched fresh BRREG data for
a company. NULL means the company has never been refreshed by the agent
(only fetched on-demand during profile view).

Revision ID: a7b8c9d0e1f2
Revises: z6a7b8c9d0e1
Create Date: 2026-04-12
"""
import sqlalchemy as sa
from alembic import op

revision = "a7b8c9d0e1f2"
down_revision = "z6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("companies", "last_refreshed_at")
