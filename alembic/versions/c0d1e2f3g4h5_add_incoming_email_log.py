"""add incoming_email_log table

Revision ID: c0d1e2f3g4h5
Revises: b9c0d1e2f3g4
Create Date: 2026-04-23 13:00:00.000000

Audit trail for every email that lands via the ACS Event Grid inbound
webhook: sender, subject, parsed tender ref, match status, any error.
Lets us debug deliverability + orphaned responses without reprocessing
MIME. PDFs themselves land in tender_offers via TenderService.upload_offer —
we don't duplicate those bytes here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c0d1e2f3g4h5"
down_revision: str | None = "b9c0d1e2f3g4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "incoming_email_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("sender", sa.String(length=320), nullable=True),
        sa.Column("recipient", sa.String(length=320), nullable=True),
        sa.Column("subject", sa.Text(), nullable=True),
        # TENDER-<tender_id>-<recipient_id> extracted from subject, null on
        # orphans. Stored as-is so debug queries don't need regex.
        sa.Column("tender_ref", sa.String(length=64), nullable=True),
        sa.Column("tender_id", sa.Integer(), nullable=True),
        sa.Column("recipient_id", sa.Integer(), nullable=True),
        # matched | orphaned | error
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attachment_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("offer_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_incoming_email_log_received_at",
        "incoming_email_log",
        [sa.text("received_at DESC")],
    )
    op.create_index(
        "ix_incoming_email_log_tender_id",
        "incoming_email_log",
        ["tender_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_incoming_email_log_tender_id", table_name="incoming_email_log")
    op.drop_index("ix_incoming_email_log_received_at", table_name="incoming_email_log")
    op.drop_table("incoming_email_log")
