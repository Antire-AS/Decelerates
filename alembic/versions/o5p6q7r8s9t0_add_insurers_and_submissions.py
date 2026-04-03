"""add insurers and submissions tables

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-04-03
"""
from alembic import op

revision = "o5p6q7r8s9t0"
down_revision = "n4o5p6q7r8s9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'submission_status') "
        "THEN CREATE TYPE submission_status AS ENUM ('pending', 'quoted', 'declined', 'withdrawn'); "
        "END IF; END $$"
    )

    op.execute("""
        CREATE TABLE IF NOT EXISTS insurers (
            id            SERIAL PRIMARY KEY,
            firm_id       INTEGER NOT NULL REFERENCES broker_firms(id) ON DELETE CASCADE,
            name          VARCHAR NOT NULL,
            org_number    VARCHAR(9),
            contact_name  VARCHAR,
            contact_email VARCHAR,
            contact_phone VARCHAR,
            appetite      JSONB,
            notes         TEXT,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_insurers_id ON insurers (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_insurers_firm_id ON insurers (firm_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id                  SERIAL PRIMARY KEY,
            orgnr               VARCHAR(9) NOT NULL,
            firm_id             INTEGER NOT NULL REFERENCES broker_firms(id) ON DELETE RESTRICT,
            insurer_id          INTEGER NOT NULL REFERENCES insurers(id) ON DELETE CASCADE,
            product_type        VARCHAR NOT NULL,
            requested_at        DATE,
            status              submission_status NOT NULL DEFAULT 'pending',
            premium_offered_nok FLOAT,
            notes               TEXT,
            created_by_email    VARCHAR,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_submissions_id ON submissions (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_submissions_orgnr ON submissions (orgnr)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_submissions_firm_id ON submissions (firm_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_submissions_insurer_id ON submissions (insurer_id)")

    op.execute(
        "ALTER TABLE policies "
        "ADD COLUMN IF NOT EXISTS insurer_id INTEGER REFERENCES insurers(id) ON DELETE SET NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE policies DROP COLUMN IF EXISTS insurer_id")
    op.execute("DROP TABLE IF EXISTS submissions")
    op.execute("DROP TABLE IF EXISTS insurers")
    op.execute("DROP TYPE IF EXISTS submission_status")
