"""Company domain models — master records, financial history, PDF sources, notes, chunks."""
from sqlalchemy import Column, DateTime, Float, Integer, JSON, String, UniqueConstraint
from pgvector.sqlalchemy import Vector

from api.models._base import Base, EMBEDDING_DIM


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
    antall_ansatte = Column(Integer)

    regnskap_raw = Column(JSON)
    pep_raw = Column(JSON)
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_refreshed_at = Column(DateTime(timezone=True), nullable=True)


class CompanyNote(Base):
    __tablename__ = "company_notes"

    id = Column(Integer, primary_key=True, index=True)
    orgnr = Column(String(9), index=True, nullable=False)
    session_id = Column(String(36), nullable=True, index=True)
    question = Column(String, nullable=False)
    answer = Column(String, nullable=False)
    created_at = Column(String, nullable=False)
    embedding = Column(Vector(EMBEDDING_DIM), nullable=True)


class CompanyHistory(Base):
    __tablename__ = "company_history"

    id              = Column(Integer, primary_key=True, index=True)
    orgnr           = Column(String(9), index=True, nullable=False)
    year            = Column(Integer, nullable=False)
    source          = Column(String, nullable=False)
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
    blob_url = Column(String, nullable=True)
    label    = Column(String)
    added_at = Column(String)

    __table_args__ = (
        UniqueConstraint("orgnr", "year", name="uq_pdf_source"),
    )


class CompanyChunk(Base):
    """Individual text chunks from company documents, stored with embeddings for LangChain RAG."""
    __tablename__ = "company_chunks"

    id         = Column(Integer, primary_key=True, index=True)
    orgnr      = Column(String(9), index=True, nullable=False)
    source     = Column(String, nullable=False)
    chunk_text = Column(String, nullable=False)
    embedding  = Column(Vector(EMBEDDING_DIM), nullable=True)
    created_at = Column(String, nullable=False)
