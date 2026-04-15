"""Add tenders, tender_recipients, tender_offers, and coverage_analyses tables.

Revision ID: d0e1f2g3h4i5
Revises: c9d0e1f2g3h4
Create Date: 2026-04-15
"""
from alembic import op

revision = "d0e1f2g3h4i5"
down_revision = "c9d0e1f2g3h4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enum types ───────────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE tender_status AS ENUM ('draft','sent','closed','analysed');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE tender_recipient_status AS ENUM ('pending','sent','received','declined');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)

    # ── Tenders ──────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS tenders (
            id               SERIAL PRIMARY KEY,
            orgnr            VARCHAR(9) NOT NULL,
            firm_id          INTEGER NOT NULL REFERENCES broker_firms(id) ON DELETE CASCADE,
            created_by_email VARCHAR,
            title            VARCHAR NOT NULL,
            product_types    JSONB NOT NULL DEFAULT '[]',
            deadline         DATE,
            notes            TEXT,
            status           tender_status NOT NULL DEFAULT 'draft',
            analysis_result  JSONB,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_tenders_orgnr ON tenders (orgnr)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tenders_firm_id ON tenders (firm_id)")

    # ── Tender recipients ────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS tender_recipients (
            id             SERIAL PRIMARY KEY,
            tender_id      INTEGER NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
            insurer_name   VARCHAR NOT NULL,
            insurer_email  VARCHAR,
            status         tender_recipient_status NOT NULL DEFAULT 'pending',
            sent_at        TIMESTAMPTZ,
            response_at    TIMESTAMPTZ,
            created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_tender_recipients_tender_id ON tender_recipients (tender_id)")

    # ── Tender offers (PDF responses from insurers) ──────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS tender_offers (
            id               SERIAL PRIMARY KEY,
            tender_id        INTEGER NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
            recipient_id     INTEGER REFERENCES tender_recipients(id) ON DELETE SET NULL,
            insurer_name     VARCHAR NOT NULL,
            filename         VARCHAR NOT NULL,
            pdf_content      BYTEA NOT NULL,
            extracted_text   TEXT,
            extracted_data   JSONB,
            uploaded_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_tender_offers_tender_id ON tender_offers (tender_id)")

    # ── Coverage analyses ────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS coverage_analyses (
            id                 SERIAL PRIMARY KEY,
            orgnr              VARCHAR(9) NOT NULL,
            firm_id            INTEGER NOT NULL REFERENCES broker_firms(id) ON DELETE CASCADE,
            document_id        INTEGER REFERENCES insurance_documents(id) ON DELETE SET NULL,
            title              VARCHAR NOT NULL,
            insurer            VARCHAR,
            product_type       VARCHAR,
            filename           VARCHAR,
            pdf_content        BYTEA,
            extracted_text     TEXT,
            coverage_data      JSONB,
            premium_nok        DOUBLE PRECISION,
            deductible_nok     DOUBLE PRECISION,
            coverage_sum_nok   DOUBLE PRECISION,
            status             VARCHAR NOT NULL DEFAULT 'pending',
            created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_coverage_analyses_orgnr ON coverage_analyses (orgnr)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_coverage_analyses_firm_id ON coverage_analyses (firm_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS coverage_analyses")
    op.execute("DROP TABLE IF EXISTS tender_offers")
    op.execute("DROP TABLE IF EXISTS tender_recipients")
    op.execute("DROP TABLE IF EXISTS tenders")
    op.execute("DROP TYPE IF EXISTS tender_recipient_status")
    op.execute("DROP TYPE IF EXISTS tender_status")
