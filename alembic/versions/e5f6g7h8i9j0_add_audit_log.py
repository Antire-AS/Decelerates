"""add audit_log table

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-03-24 00:03:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6g7h8i9j0"
down_revision: str | None = "d4e5f6g7h8i9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '60s'")
    op.execute(
        "CREATE TABLE IF NOT EXISTS audit_log ("
        "  id SERIAL NOT NULL, orgnr VARCHAR(9), actor_email VARCHAR,"
        "  action VARCHAR NOT NULL, detail VARCHAR,"
        "  created_at TIMESTAMPTZ NOT NULL, PRIMARY KEY (id)"
        ")"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_log_orgnr ON audit_log (orgnr)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_log_created_at ON audit_log (created_at)")


def downgrade() -> None:
    op.drop_table("audit_log")
