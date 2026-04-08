"""add job_queue table for durable background jobs

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-03-26
"""
from alembic import op

revision = "l2m3n4o5p6q7"
down_revision = "k1l2m3n4o5p6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS job_queue (
            id          SERIAL PRIMARY KEY,
            job_type    VARCHAR(100) NOT NULL,
            payload     JSONB,
            status      VARCHAR(20) NOT NULL DEFAULT 'pending',
            attempts    INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 3,
            created_at  TIMESTAMP WITH TIME ZONE NOT NULL,
            scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            started_at  TIMESTAMP WITH TIME ZONE,
            finished_at TIMESTAMP WITH TIME ZONE,
            error       TEXT
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_job_queue_status ON job_queue (status, scheduled_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS job_queue")
