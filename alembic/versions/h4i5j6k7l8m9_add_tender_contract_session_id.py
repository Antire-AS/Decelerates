"""Add contract_session_id to tenders so e-sign webhooks can route back.

When the broker clicks "Send kontrakt til kunde", the backend creates a
DocuSeal/Signicat signing session and gets back a session_id. Storing it
on the tender row lets the provider's webhook callback find the tender
and update its status without having to invert-lookup through sessions
stored elsewhere.

Safe for zero-downtime: ADD COLUMN IF NOT EXISTS + nullable column.

Revision ID: h4i5j6k7l8m9
Revises: g3h4i5j6k7l8
Create Date: 2026-04-21
"""

from alembic import op

revision = "h4i5j6k7l8m9"
down_revision = "g3h4i5j6k7l8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE tenders ADD COLUMN IF NOT EXISTS contract_session_id VARCHAR(128)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_tenders_contract_session_id "
        "ON tenders (contract_session_id) WHERE contract_session_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_tenders_contract_session_id")
    op.drop_column("tenders", "contract_session_id")
