"""add blob_url to company_pdf_sources

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-03-28
"""
from alembic import op

revision = "m3n4o5p6q7r8"
down_revision = "l2m3n4o5p6q7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE company_pdf_sources ADD COLUMN IF NOT EXISTS blob_url VARCHAR"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE company_pdf_sources DROP COLUMN IF EXISTS blob_url"
    )
