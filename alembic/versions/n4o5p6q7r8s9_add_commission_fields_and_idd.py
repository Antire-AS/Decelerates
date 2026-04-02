"""add commission fields to policies and idd_behovsanalyse table

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-04-02
"""
from alembic import op

revision = "n4o5p6q7r8s9"
down_revision = "m3n4o5p6q7r8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Commission fields on policies
    op.execute(
        "ALTER TABLE policies "
        "ADD COLUMN IF NOT EXISTS commission_rate_pct FLOAT, "
        "ADD COLUMN IF NOT EXISTS commission_amount_nok FLOAT"
    )

    # IDD behovsanalyse table
    op.execute("""
        CREATE TABLE IF NOT EXISTS idd_behovsanalyse (
            id                     SERIAL PRIMARY KEY,
            orgnr                  VARCHAR(9) NOT NULL,
            firm_id                INTEGER NOT NULL,
            created_by_email       VARCHAR,
            created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
            client_name            VARCHAR,
            client_contact_name    VARCHAR,
            client_contact_email   VARCHAR,
            existing_insurance     JSONB,
            risk_appetite          VARCHAR,
            property_owned         BOOLEAN DEFAULT FALSE,
            has_employees          BOOLEAN DEFAULT FALSE,
            has_vehicles           BOOLEAN DEFAULT FALSE,
            has_professional_liability BOOLEAN DEFAULT FALSE,
            has_cyber_risk         BOOLEAN DEFAULT FALSE,
            annual_revenue_nok     FLOAT,
            special_requirements   TEXT,
            recommended_products   JSONB,
            advisor_notes          TEXT,
            suitability_basis      TEXT,
            fee_basis              VARCHAR,
            fee_amount_nok         FLOAT
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_idd_behovsanalyse_orgnr "
        "ON idd_behovsanalyse (orgnr)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS idd_behovsanalyse")
    op.execute("ALTER TABLE policies DROP COLUMN IF EXISTS commission_rate_pct")
    op.execute("ALTER TABLE policies DROP COLUMN IF EXISTS commission_amount_nok")
