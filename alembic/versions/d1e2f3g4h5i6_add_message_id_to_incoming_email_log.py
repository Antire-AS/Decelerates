"""add message_id to incoming_email_log for webhook dedup

Revision ID: d1e2f3g4h5i6
Revises: c0d1e2f3g4h5
Create Date: 2026-04-23 22:10:00.000000

Graph can replay the same change notification if our 2xx ack is
delivered late or lost. Without a stable identifier we'd happily
insert the same TenderOffer twice. `internetMessageId` (RFC822
Message-ID) is preserved across retries and is populated by every mail
server, so it's the natural dedup key.

Nullable because existing rows pre-dedup don't have one, and ACS rows
may land before we plumb Message-ID extraction there. Partial unique
index (WHERE message_id IS NOT NULL) enforces dedup on new rows without
breaking the migration on existing data.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d1e2f3g4h5i6"
down_revision: str | Sequence[str] | None = "c0d1e2f3g4h5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "incoming_email_log",
        sa.Column("message_id", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_incoming_email_log_message_id_unique",
        "incoming_email_log",
        ["message_id"],
        unique=True,
        postgresql_where=sa.text("message_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_incoming_email_log_message_id_unique",
        table_name="incoming_email_log",
    )
    op.drop_column("incoming_email_log", "message_id")
