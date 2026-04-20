"""Add user_chat_messages table for per-user chat memory.

Enables the knowledge chat and the per-company chat tab to remember past
turns so brokers don't have to re-explain context every session. Each row
is a single turn (user question or assistant answer), grouped by
(user_oid, orgnr) — orgnr is NULL for the general knowledge chat.

Safe for zero-downtime: CREATE TABLE IF NOT EXISTS + pg_try_advisory_lock
pattern is not needed here (new table, no existing rows to lock on), but
IF NOT EXISTS guards against double-apply in replica rollout.

Revision ID: a7b8c9d0e1f2
Revises: z6a7b8c9d0e1
Create Date: 2026-04-20
"""

from alembic import op

revision = "a7b8c9d0e1f2"
down_revision = "z6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_chat_messages (
            id SERIAL PRIMARY KEY,
            user_oid VARCHAR(64) NOT NULL,
            orgnr VARCHAR(9) NULL,
            role VARCHAR(16) NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_chat_messages_user_oid "
        "ON user_chat_messages (user_oid)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_chat_messages_orgnr "
        "ON user_chat_messages (orgnr)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_chat_messages_user_orgnr_created "
        "ON user_chat_messages (user_oid, orgnr, created_at)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_chat_messages")
