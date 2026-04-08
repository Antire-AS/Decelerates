"""add last_renewal_notified_days to policies

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-03-26
"""
from alembic import op

revision = "j0k1l2m3n4o5"
down_revision = "i9j0k1l2m3n4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE policies
        ADD COLUMN IF NOT EXISTS last_renewal_notified_days INTEGER
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE policies DROP COLUMN IF EXISTS last_renewal_notified_days")
