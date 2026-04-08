"""add deleted_at to companies for GDPR soft-delete

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-03-26
"""
from alembic import op

revision = "k1l2m3n4o5p6"
down_revision = "j0k1l2m3n4o5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE companies
        ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE companies DROP COLUMN IF EXISTS deleted_at")
