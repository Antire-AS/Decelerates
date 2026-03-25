"""add antall_ansatte to companies

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = "i9j0k1l2m3n4"
down_revision = "h8i9j0k1l2m3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE companies
        ADD COLUMN IF NOT EXISTS antall_ansatte INTEGER
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE companies DROP COLUMN IF EXISTS antall_ansatte")
