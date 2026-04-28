"""add tender customer portal columns

Revision ID: p4q5r6s7t8u9
Revises: o3p4q5r6s7t8
Create Date: 2026-04-28 12:50:00.000000

P4 from anbud-expansion roadmap. Lets the broker generate a
customer-facing URL after running AI analysis. Customer opens it,
reviews, approves or rejects.

Columns on `tenders` (all nullable):
- customer_access_token (varchar 64) + partial unique index
- customer_email (varchar)
- customer_approval_status (varchar 16: pending/approved/rejected)
- customer_approval_at (timestamptz)

Safety patterns from feedback_deploy_migration_safety.md:
- IF NOT EXISTS — idempotent
- lock_timeout 5s — bail out on contention
- statement_timeout 15s — second-line guard
"""

from collections.abc import Sequence

from alembic import op


revision: str = "p4q5r6s7t8u9"
down_revision: str | None = "o3p4q5r6s7t8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Same lock-avoidance pattern as o3p4q5r6s7t8: skip ALTER if columns
    # are already there. Avoids ACCESS EXCLUSIVE contention when a
    # parallel revision is serving SELECTs on `tenders` mid-deploy.
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tenders'
                  AND column_name = 'customer_access_token'
            ) THEN
                SET LOCAL lock_timeout = '5s';
                SET LOCAL statement_timeout = '15s';
                ALTER TABLE tenders
                    ADD COLUMN customer_access_token VARCHAR(64),
                    ADD COLUMN customer_email VARCHAR,
                    ADD COLUMN customer_approval_status VARCHAR(16),
                    ADD COLUMN customer_approval_at TIMESTAMPTZ;
            END IF;
        END $$;
    """)
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_tenders_customer_access_token_unique "
        "ON tenders (customer_access_token) WHERE customer_access_token IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("SET LOCAL statement_timeout = '15s'")
    op.execute("DROP INDEX IF EXISTS ix_tenders_customer_access_token_unique")
    op.execute("ALTER TABLE tenders DROP COLUMN IF EXISTS customer_approval_at")
    op.execute("ALTER TABLE tenders DROP COLUMN IF EXISTS customer_approval_status")
    op.execute("ALTER TABLE tenders DROP COLUMN IF EXISTS customer_email")
    op.execute("ALTER TABLE tenders DROP COLUMN IF EXISTS customer_access_token")
