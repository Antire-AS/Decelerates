"""Add renewal_brief + renewal_email_draft to policies.

These columns cache the AI-generated renewal brief and client email draft
so the daily cron doesn't re-call the LLM on every run. Both are nullable —
existing policies are unaffected until the renewal agent processes them.

Revision ID: y5z6a7b8c9d0
Revises: x4y5z6a7b8c9
Create Date: 2026-04-12
"""
import sqlalchemy as sa
from alembic import op

revision = "y5z6a7b8c9d0"
down_revision = "x4y5z6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use raw SQL with IF NOT EXISTS for idempotency — a previous container
    # may have added the columns before crashing without committing the
    # alembic_version update.
    op.execute("ALTER TABLE policies ADD COLUMN IF NOT EXISTS renewal_brief VARCHAR")
    op.execute("ALTER TABLE policies ADD COLUMN IF NOT EXISTS renewal_email_draft VARCHAR")


def downgrade() -> None:
    op.drop_column("policies", "renewal_email_draft")
    op.drop_column("policies", "renewal_brief")
