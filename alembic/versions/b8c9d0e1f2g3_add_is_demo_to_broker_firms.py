"""Add is_demo column to broker_firms + tag firm_id=1 as demo.

Revision ID: b8c9d0e1f2g3
Revises: a7b8c9d0e1f2
Create Date: 2026-04-14
"""
import sqlalchemy as sa
from alembic import op

revision = "b8c9d0e1f2g3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE broker_firms ADD COLUMN IF NOT EXISTS is_demo BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("UPDATE broker_firms SET is_demo = TRUE WHERE id = 1")


def downgrade() -> None:
    op.drop_column("broker_firms", "is_demo")
