import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, JSON, LargeBinary, text, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker
from pgvector.sqlalchemy import Vector

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://brokeruser:brokerpass@localhost:5432/brokerdb",
)

# Normalise to psycopg3 driver (psycopg2-binary has no ARM64 Windows wheel)
_db_url = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1).replace(
    "postgresql+psycopg2://", "postgresql+psycopg://", 1
)

engine = create_engine(_db_url, echo=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

# Dimensions for voyage-3-lite embeddings
EMBEDDING_DIM = 512


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    orgnr = Column(String(9), unique=True, index=True, nullable=False)
    navn = Column(String, index=True)
    organisasjonsform_kode = Column(String(10))
    kommune = Column(String(100))
    land = Column(String(50))
    naeringskode1 = Column(String(20))
    naeringskode1_beskrivelse = Column(String(255))

    regnskapsår = Column(Integer)
    sum_driftsinntekter = Column(Float)
    sum_egenkapital = Column(Float)
    sum_eiendeler = Column(Float)
    equity_ratio = Column(Float)
    risk_score = Column(Integer)

    regnskap_raw = Column(JSON)
    pep_raw = Column(JSON)


class CompanyNote(Base):
    __tablename__ = "company_notes"

    id = Column(Integer, primary_key=True, index=True)
    orgnr = Column(String(9), index=True, nullable=False)
    question = Column(String, nullable=False)
    answer = Column(String, nullable=False)
    created_at = Column(String, nullable=False)
    embedding = Column(Vector(EMBEDDING_DIM), nullable=True)


class CompanyHistory(Base):
    __tablename__ = "company_history"

    id              = Column(Integer, primary_key=True, index=True)
    orgnr           = Column(String(9), index=True, nullable=False)
    year            = Column(Integer, nullable=False)
    source          = Column(String, nullable=False)   # "brreg" | "pdf"
    pdf_url         = Column(String, nullable=True)

    revenue         = Column(Float)
    net_result      = Column(Float)
    equity          = Column(Float)
    total_assets    = Column(Float)
    equity_ratio    = Column(Float)
    short_term_debt = Column(Float)
    long_term_debt  = Column(Float)
    antall_ansatte  = Column(Integer)
    currency        = Column(String(10), default="NOK")

    raw             = Column(JSON)

    __table_args__ = (
        UniqueConstraint("orgnr", "year", name="uq_company_history"),
    )


class CompanyPdfSource(Base):
    __tablename__ = "company_pdf_sources"

    id       = Column(Integer, primary_key=True, index=True)
    orgnr    = Column(String(9), index=True, nullable=False)
    year     = Column(Integer, nullable=False)
    pdf_url  = Column(String, nullable=False)
    label    = Column(String)
    added_at = Column(String)

    __table_args__ = (
        UniqueConstraint("orgnr", "year", name="uq_pdf_source"),
    )


class BrokerSettings(Base):
    __tablename__ = "broker_settings"

    id            = Column(Integer, primary_key=True, default=1)
    firm_name     = Column(String, nullable=False, default="")
    orgnr         = Column(String(9))
    address       = Column(String)
    contact_name  = Column(String)
    contact_email = Column(String)
    contact_phone = Column(String)
    updated_at    = Column(String)   # ISO timestamp


class SlaAgreement(Base):
    __tablename__ = "sla_agreements"

    id              = Column(Integer, primary_key=True)
    created_at      = Column(String, nullable=False)
    broker_snapshot = Column(JSON)     # copy of BrokerSettings at creation time
    client_orgnr    = Column(String(9), index=True)
    client_navn     = Column(String)
    client_adresse  = Column(String)
    client_kontakt  = Column(String)
    start_date      = Column(String)
    account_manager = Column(String)
    insurance_lines = Column(JSON)     # ["Eiendom", "Ansvar", "Cyber", ...]
    fee_structure   = Column(JSON)     # {"lines": [{"line": "Eiendom", "type": "provisjon", "rate": 12.5}]}
    status          = Column(String, default="draft")   # "draft" | "active" | "terminated"
    form_data       = Column(JSON)     # full snapshot for PDF regeneration


class InsuranceOffer(Base):
    __tablename__ = "insurance_offers"

    id             = Column(Integer, primary_key=True)
    orgnr          = Column(String(9), index=True, nullable=False)
    filename       = Column(String, nullable=False)
    insurer_name   = Column(String)          # e.g. "If Skadeforsikring"
    uploaded_at    = Column(String, nullable=False)
    pdf_content    = Column(LargeBinary, nullable=False)
    extracted_text = Column(String)          # cached pdfplumber extraction


class InsuranceDocument(Base):
    __tablename__ = "insurance_documents"

    id             = Column(Integer, primary_key=True)
    title          = Column(String, nullable=False)
    category       = Column(String)          # "næringslivsforsikring" | "personalforsikring" | "reise" | "annet"
    insurer        = Column(String)          # "If", "Gjensidige", "Fremtind"
    year           = Column(Integer)         # 2025, 2026
    period         = Column(String)          # "aktiv" | "historisk"
    orgnr          = Column(String(9))       # optional — klientens orgnr
    filename       = Column(String, nullable=False)
    pdf_content    = Column(LargeBinary, nullable=False)
    extracted_text = Column(String)          # cached pdfplumber extraction
    uploaded_at    = Column(String, nullable=False)
    tags           = Column(String, nullable=True)  # comma-separated tags


class BrokerNote(Base):
    __tablename__ = "broker_notes"

    id         = Column(Integer, primary_key=True, index=True)
    orgnr      = Column(String(9), index=True, nullable=False)
    text       = Column(String, nullable=False)
    created_at = Column(String, nullable=False)


class CompanyChunk(Base):
    """Individual text chunks from company documents, stored with embeddings for LangChain RAG."""
    __tablename__ = "company_chunks"

    id         = Column(Integer, primary_key=True, index=True)
    orgnr      = Column(String(9), index=True, nullable=False)
    source     = Column(String, nullable=False)   # e.g. "annual_report_2023", "offer_42", "custom_note"
    chunk_text = Column(String, nullable=False)
    embedding  = Column(Vector(EMBEDDING_DIM), nullable=True)
    created_at = Column(String, nullable=False)


def init_db():
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
