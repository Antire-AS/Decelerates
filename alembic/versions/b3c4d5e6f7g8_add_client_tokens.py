"""add client_tokens table

Revision ID: b3c4d5e6f7g8
Revises: a2b3c4d5e6f7
Create Date: 2026-03-23 00:01:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3c4d5e6f7g8"
down_revision: str | None = "a2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "client_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token", sa.String(64), nullable=False, unique=True),
        sa.Column("orgnr", sa.String(9), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_client_tokens_token", "client_tokens", ["token"])
    op.create_index("ix_client_tokens_orgnr", "client_tokens", ["orgnr"])


def downgrade() -> None:
    op.drop_table("client_tokens")
