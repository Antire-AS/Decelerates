"""Add company_whiteboards table for per-user per-company focus workspace.

Each broker gets a whiteboard per company they work on — a place to collect
facts pulled from oversikt/økonomi/forsikring tabs, add freeform notes, and
keep an AI-generated summary. One row per (user, orgnr); updates upsert.

Safe for zero-downtime: pure new table with CREATE IF NOT EXISTS guard.

Revision ID: f2g3h4i5j6k7
Revises: e1f2g3h4i5j6
Create Date: 2026-04-20
"""

from alembic import op

revision = "f2g3h4i5j6k7"
down_revision = "e1f2g3h4i5j6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS company_whiteboards (
            id SERIAL PRIMARY KEY,
            orgnr VARCHAR(9) NOT NULL,
            user_oid VARCHAR(64) NOT NULL,
            items JSONB NOT NULL DEFAULT '[]'::jsonb,
            notes TEXT NULL,
            ai_summary TEXT NULL,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_company_whiteboards_orgnr "
        "ON company_whiteboards (orgnr)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_company_whiteboards_user_oid "
        "ON company_whiteboards (user_oid)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_company_whiteboards_orgnr_user "
        "ON company_whiteboards (orgnr, user_oid)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS company_whiteboards")
