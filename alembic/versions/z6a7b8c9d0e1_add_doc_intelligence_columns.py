"""Add auto-analysis columns to insurance_documents.

These columns cache AI-extracted data so brokers see structured insights
immediately after upload — no manual "Extract" click needed.

Revision ID: z6a7b8c9d0e1
Revises: y5z6a7b8c9d0
Create Date: 2026-04-12
"""
import sqlalchemy as sa
from alembic import op

revision = "z6a7b8c9d0e1"
down_revision = "y5z6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("insurance_documents", sa.Column("cached_keypoints", sa.JSON(), nullable=True))
    op.add_column("insurance_documents", sa.Column("parsed_premium_nok", sa.Float(), nullable=True))
    op.add_column("insurance_documents", sa.Column("parsed_coverage_nok", sa.Float(), nullable=True))
    op.add_column("insurance_documents", sa.Column("parsed_deductible_nok", sa.Float(), nullable=True))
    op.add_column("insurance_documents", sa.Column("auto_comparison_result", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("insurance_documents", "auto_comparison_result")
    op.drop_column("insurance_documents", "parsed_deductible_nok")
    op.drop_column("insurance_documents", "parsed_coverage_nok")
    op.drop_column("insurance_documents", "parsed_premium_nok")
    op.drop_column("insurance_documents", "cached_keypoints")
