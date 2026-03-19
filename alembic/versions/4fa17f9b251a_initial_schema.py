"""initial schema

Revision ID: 4fa17f9b251a
Revises:
Create Date: 2026-03-19 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "4fa17f9b251a"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 512


def upgrade() -> None:
    # Enable pgvector extension — required before creating Vector columns.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("orgnr", sa.String(length=9), nullable=False),
        sa.Column("navn", sa.String(), nullable=True),
        sa.Column("organisasjonsform_kode", sa.String(length=10), nullable=True),
        sa.Column("kommune", sa.String(length=100), nullable=True),
        sa.Column("land", sa.String(length=50), nullable=True),
        sa.Column("naeringskode1", sa.String(length=20), nullable=True),
        sa.Column("naeringskode1_beskrivelse", sa.String(length=255), nullable=True),
        sa.Column("regnskapsår", sa.Integer(), nullable=True),
        sa.Column("sum_driftsinntekter", sa.Float(), nullable=True),
        sa.Column("sum_egenkapital", sa.Float(), nullable=True),
        sa.Column("sum_eiendeler", sa.Float(), nullable=True),
        sa.Column("equity_ratio", sa.Float(), nullable=True),
        sa.Column("risk_score", sa.Integer(), nullable=True),
        sa.Column("regnskap_raw", sa.JSON(), nullable=True),
        sa.Column("pep_raw", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_companies_id"), "companies", ["id"], unique=False)
    op.create_index(op.f("ix_companies_navn"), "companies", ["navn"], unique=False)
    op.create_index(op.f("ix_companies_orgnr"), "companies", ["orgnr"], unique=True)

    op.create_table(
        "company_notes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("orgnr", sa.String(length=9), nullable=False),
        sa.Column("question", sa.String(), nullable=False),
        sa.Column("answer", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_company_notes_id"), "company_notes", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_company_notes_orgnr"), "company_notes", ["orgnr"], unique=False
    )

    op.create_table(
        "company_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("orgnr", sa.String(length=9), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("pdf_url", sa.String(), nullable=True),
        sa.Column("revenue", sa.Float(), nullable=True),
        sa.Column("net_result", sa.Float(), nullable=True),
        sa.Column("equity", sa.Float(), nullable=True),
        sa.Column("total_assets", sa.Float(), nullable=True),
        sa.Column("equity_ratio", sa.Float(), nullable=True),
        sa.Column("short_term_debt", sa.Float(), nullable=True),
        sa.Column("long_term_debt", sa.Float(), nullable=True),
        sa.Column("antall_ansatte", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("raw", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("orgnr", "year", name="uq_company_history"),
    )
    op.create_index(
        op.f("ix_company_history_id"), "company_history", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_company_history_orgnr"), "company_history", ["orgnr"], unique=False
    )

    op.create_table(
        "company_pdf_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("orgnr", sa.String(length=9), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("pdf_url", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("added_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("orgnr", "year", name="uq_pdf_source"),
    )
    op.create_index(
        op.f("ix_company_pdf_sources_id"),
        "company_pdf_sources",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_company_pdf_sources_orgnr"),
        "company_pdf_sources",
        ["orgnr"],
        unique=False,
    )

    op.create_table(
        "broker_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("firm_name", sa.String(), nullable=False),
        sa.Column("orgnr", sa.String(length=9), nullable=True),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("contact_name", sa.String(), nullable=True),
        sa.Column("contact_email", sa.String(), nullable=True),
        sa.Column("contact_phone", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "sla_agreements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("broker_snapshot", sa.JSON(), nullable=True),
        sa.Column("client_orgnr", sa.String(length=9), nullable=True),
        sa.Column("client_navn", sa.String(), nullable=True),
        sa.Column("client_adresse", sa.String(), nullable=True),
        sa.Column("client_kontakt", sa.String(), nullable=True),
        sa.Column("start_date", sa.String(), nullable=True),
        sa.Column("account_manager", sa.String(), nullable=True),
        sa.Column("insurance_lines", sa.JSON(), nullable=True),
        sa.Column("fee_structure", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("form_data", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_sla_agreements_client_orgnr"),
        "sla_agreements",
        ["client_orgnr"],
        unique=False,
    )

    op.create_table(
        "insurance_offers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("orgnr", sa.String(length=9), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("insurer_name", sa.String(), nullable=True),
        sa.Column("uploaded_at", sa.String(), nullable=False),
        sa.Column("pdf_content", sa.LargeBinary(), nullable=False),
        sa.Column("extracted_text", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_insurance_offers_orgnr"),
        "insurance_offers",
        ["orgnr"],
        unique=False,
    )

    op.create_table(
        "insurance_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("insurer", sa.String(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("period", sa.String(), nullable=True),
        sa.Column("orgnr", sa.String(length=9), nullable=True),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("pdf_content", sa.LargeBinary(), nullable=False),
        sa.Column("extracted_text", sa.String(), nullable=True),
        sa.Column("uploaded_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "broker_notes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("orgnr", sa.String(length=9), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_broker_notes_id"), "broker_notes", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_broker_notes_orgnr"), "broker_notes", ["orgnr"], unique=False
    )

    op.create_table(
        "company_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("orgnr", sa.String(length=9), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("chunk_text", sa.String(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_company_chunks_id"), "company_chunks", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_company_chunks_orgnr"), "company_chunks", ["orgnr"], unique=False
    )


def downgrade() -> None:
    op.drop_table("company_chunks")
    op.drop_table("broker_notes")
    op.drop_table("insurance_documents")
    op.drop_table("insurance_offers")
    op.drop_table("sla_agreements")
    op.drop_table("broker_settings")
    op.drop_table("company_pdf_sources")
    op.drop_table("company_history")
    op.drop_table("company_notes")
    op.drop_table("companies")
