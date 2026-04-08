"""Signicat e-sign columns on recommendations — plan §🟢 #11.

All three columns are nullable; existing recommendation rows are unaffected.
The signing workflow is opt-in: POST /recommendations/{id}/sign creates a
Signicat session and POST /webhooks/signicat updates the row when the
client completes signing.

Revision ID: w3x4y5z6a7b8
Revises: v2w3x4y5z6a7
Create Date: 2026-04-07
"""
import sqlalchemy as sa
from alembic import op

revision = "w3x4y5z6a7b8"
down_revision = "v2w3x4y5z6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("recommendations", sa.Column("signing_session_id", sa.String(), nullable=True))
    op.add_column("recommendations", sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("recommendations", sa.Column("signed_pdf_blob_url", sa.String(), nullable=True))
    op.create_index(
        "idx_recommendations_signing_session_id",
        "recommendations",
        ["signing_session_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_recommendations_signing_session_id", table_name="recommendations")
    op.drop_column("recommendations", "signed_pdf_blob_url")
    op.drop_column("recommendations", "signed_at")
    op.drop_column("recommendations", "signing_session_id")
