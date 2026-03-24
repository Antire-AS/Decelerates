"""add session_id to company_notes

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-03-24 13:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "h8i9j0k1l2m3"
down_revision: str | None = "g7h8i9j0k1l2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "company_notes",
        sa.Column("session_id", sa.String(36), nullable=True),
    )
    op.create_index("ix_company_notes_session_id", "company_notes", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_company_notes_session_id", table_name="company_notes")
    op.drop_column("company_notes", "session_id")
