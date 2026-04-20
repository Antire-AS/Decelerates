"""Add access_token to tender_recipients for insurer portal links.

The broker generates one tender, sends invitations to several insurers.
Each insurer needs a unique, long-lived link that lets them upload their
quote without having to log into the broker's account. Mirrors the
pattern already used by `client_access_tokens` for client portals.

Safe for zero-downtime: ADD COLUMN IF NOT EXISTS with NULL default.

Revision ID: g3h4i5j6k7l8
Revises: f2g3h4i5j6k7
Create Date: 2026-04-20
"""

from alembic import op

revision = "g3h4i5j6k7l8"
down_revision = "f2g3h4i5j6k7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE tender_recipients ADD COLUMN IF NOT EXISTS access_token VARCHAR(64)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_tender_recipients_access_token "
        "ON tender_recipients (access_token) WHERE access_token IS NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS ix_tender_recipients_access_token"
    )
    op.drop_column("tender_recipients", "access_token")
