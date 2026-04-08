"""add recommendations table

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-04-03
"""
from alembic import op

revision = "p6q7r8s9t0u1"
down_revision = "o5p6q7r8s9t0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS recommendations (
            id                  SERIAL PRIMARY KEY,
            orgnr               VARCHAR(9) NOT NULL,
            firm_id             INTEGER NOT NULL REFERENCES broker_firms(id) ON DELETE RESTRICT,
            created_by_email    VARCHAR,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            idd_id              INTEGER REFERENCES idd_behovsanalyse(id) ON DELETE SET NULL,
            submission_ids      JSONB,
            recommended_insurer VARCHAR,
            rationale_text      TEXT,
            pdf_content         BYTEA
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_recommendations_orgnr ON recommendations (orgnr)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_recommendations_firm_id ON recommendations (firm_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS recommendations")
