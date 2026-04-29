"""Add tender_chat_sessions and tender_chat_messages tables.

Revision ID: 2dd4ee81fd23
Revises: z6a7b8c9d0e1
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa

revision = "2dd4ee81fd23"
down_revision = ("z6a7b8c9d0e1", "d1e2f3g4h5i6")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tender_chat_sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_oid", sa.String(64), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_tender_chat_sessions_user", "tender_chat_sessions",
                    ["user_oid", "updated_at"])

    op.create_table(
        "tender_chat_messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Integer,
                  sa.ForeignKey("tender_chat_sessions.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_tender_chat_messages_session", "tender_chat_messages",
                    ["session_id", "created_at"])


def downgrade() -> None:
    op.drop_table("tender_chat_messages")
    op.drop_table("tender_chat_sessions")
