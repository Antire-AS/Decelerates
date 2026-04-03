import enum
import os
from datetime import datetime
from sqlalchemy import (
    Boolean, create_engine, Column, Date, DateTime, Enum as SAEnum,
    Integer, String, Float, JSON, LargeBinary, text, UniqueConstraint, ForeignKey, Index,
)
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

engine = create_engine(_db_url, echo=False, future=True)
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
    antall_ansatte = Column(Integer)

    regnskap_raw = Column(JSON)
    pep_raw = Column(JSON)
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)


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
    pdf_url  = Column(String, nullable=False)   # original external URL
    blob_url = Column(String, nullable=True)    # Azure Blob copy (None if not yet uploaded)
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
    signed_at       = Column(DateTime(timezone=True), nullable=True)
    signed_by       = Column(String, nullable=True)


class OfferStatus(enum.Enum):
    pending     = "pending"
    accepted    = "accepted"
    rejected    = "rejected"
    negotiating = "negotiating"


class InsuranceOffer(Base):
    __tablename__ = "insurance_offers"

    id             = Column(Integer, primary_key=True)
    orgnr          = Column(String(9), index=True, nullable=False)
    filename       = Column(String, nullable=False)
    insurer_name   = Column(String)          # e.g. "If Skadeforsikring"
    uploaded_at    = Column(String, nullable=False)
    pdf_content    = Column(LargeBinary, nullable=False)
    extracted_text = Column(String)          # cached pdfplumber extraction
    # Structured fields parsed by LLM in background after upload
    parsed_premie    = Column(String, nullable=True)
    parsed_dekning   = Column(String, nullable=True)
    parsed_egenandel = Column(String, nullable=True)
    parsed_vilkaar   = Column(String, nullable=True)
    parsed_styrker   = Column(String, nullable=True)
    parsed_svakheter = Column(String, nullable=True)
    status = Column(
        SAEnum(OfferStatus, name="offer_status", create_type=False),
        nullable=True,
        default=OfferStatus.pending,
    )


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


class Portfolio(Base):
    """A named list of companies for cross-portfolio risk analysis."""
    __tablename__ = "portfolios"

    id          = Column(Integer, primary_key=True, index=True)
    firm_id     = Column(Integer, ForeignKey("broker_firms.id", ondelete="CASCADE"), nullable=True, index=True)
    name        = Column(String, nullable=False)
    description = Column(String)
    created_at  = Column(String, nullable=False)


class PortfolioCompany(Base):
    """Junction table — which companies belong to which portfolio."""
    __tablename__ = "portfolio_companies"

    portfolio_id = Column(Integer, ForeignKey("portfolios.id", ondelete="CASCADE"), primary_key=True)
    orgnr        = Column(String(9), primary_key=True)
    added_at     = Column(String, nullable=False)


class UserRole(enum.Enum):
    admin  = "admin"
    broker = "broker"
    viewer = "viewer"


class BrokerFirm(Base):
    """Multi-tenant broker firm — all CRM data is scoped to a firm."""
    __tablename__ = "broker_firms"

    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String, nullable=False)
    orgnr      = Column(String(9), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)


class User(Base):
    """Broker user — auto-provisioned on first Azure AD login."""
    __tablename__ = "users"

    id         = Column(Integer, primary_key=True, index=True)
    firm_id    = Column(Integer, ForeignKey("broker_firms.id", ondelete="RESTRICT"), nullable=False, index=True)
    azure_oid  = Column(String(64), unique=True, nullable=False, index=True)
    email      = Column(String, nullable=False)
    name       = Column(String, nullable=False)
    role       = Column(SAEnum(UserRole, name="user_role", create_type=False), nullable=False, default=UserRole.broker)
    created_at = Column(DateTime(timezone=True), nullable=False)


class ContactPerson(Base):
    """A named contact at a client company."""
    __tablename__ = "contact_persons"

    id         = Column(Integer, primary_key=True, index=True)
    orgnr      = Column(String(9), nullable=False, index=True)
    name       = Column(String, nullable=False)
    title      = Column(String, nullable=True)
    email      = Column(String, nullable=True)
    phone      = Column(String, nullable=True)
    is_primary = Column(Boolean, default=False, nullable=False)
    notes      = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)


class PolicyStatus(enum.Enum):
    active    = "active"
    expired   = "expired"
    cancelled = "cancelled"
    pending   = "pending"


class RenewalStage(enum.Enum):
    not_started    = "not_started"
    ready_to_quote = "ready_to_quote"
    quoted         = "quoted"
    accepted       = "accepted"
    declined       = "declined"


class Policy(Base):
    """A bound insurance policy in the broker's book of business."""
    __tablename__ = "policies"

    id                  = Column(Integer, primary_key=True, index=True)
    orgnr               = Column(String(9), nullable=False, index=True)
    firm_id             = Column(Integer, ForeignKey("broker_firms.id", ondelete="RESTRICT"), nullable=False, index=True)
    contact_person_id   = Column(Integer, ForeignKey("contact_persons.id", ondelete="SET NULL"), nullable=True)
    policy_number       = Column(String(100), nullable=True)
    insurer             = Column(String, nullable=False)
    product_type        = Column(String, nullable=False)
    coverage_amount_nok = Column(Float, nullable=True)
    annual_premium_nok  = Column(Float, nullable=True)
    start_date          = Column(Date, nullable=True)
    renewal_date        = Column(Date, nullable=True, index=True)
    status              = Column(SAEnum(PolicyStatus, name="policy_status", create_type=False), nullable=False, default=PolicyStatus.active)
    renewal_stage       = Column(SAEnum(RenewalStage, name="renewal_stage", create_type=False), nullable=False, default=RenewalStage.not_started)
    notes               = Column(String, nullable=True)
    document_url        = Column(String, nullable=True)
    last_renewal_notified_days = Column(Integer, nullable=True)
    commission_rate_pct = Column(Float, nullable=True)
    commission_amount_nok = Column(Float, nullable=True)
    created_at          = Column(DateTime(timezone=True), nullable=False)
    updated_at          = Column(DateTime(timezone=True), nullable=False)


class ClaimStatus(enum.Enum):
    open      = "open"
    in_review = "in_review"
    settled   = "settled"
    rejected  = "rejected"


class Claim(Base):
    """An insurance claim managed on behalf of a client."""
    __tablename__ = "claims"

    id                   = Column(Integer, primary_key=True, index=True)
    policy_id            = Column(Integer, ForeignKey("policies.id", ondelete="CASCADE"), nullable=False, index=True)
    orgnr                = Column(String(9), nullable=False, index=True)
    firm_id              = Column(Integer, ForeignKey("broker_firms.id", ondelete="RESTRICT"), nullable=False, index=True)
    claim_number         = Column(String(100), nullable=True)
    incident_date        = Column(Date, nullable=True)
    reported_date        = Column(Date, nullable=True)
    status               = Column(SAEnum(ClaimStatus, name="claim_status", create_type=False), nullable=False, default=ClaimStatus.open)
    description          = Column(String, nullable=True)
    estimated_amount_nok = Column(Float, nullable=True)
    settled_amount_nok   = Column(Float, nullable=True)
    insurer_contact      = Column(String, nullable=True)
    notes                = Column(String, nullable=True)
    created_at           = Column(DateTime(timezone=True), nullable=False)
    updated_at           = Column(DateTime(timezone=True), nullable=False)


class ActivityType(enum.Enum):
    call    = "call"
    email   = "email"
    meeting = "meeting"
    note    = "note"
    task    = "task"


class Activity(Base):
    """CRM activity log entry — call, email, meeting, note, or task."""
    __tablename__ = "activities"

    id               = Column(Integer, primary_key=True, index=True)
    orgnr            = Column(String(9), nullable=True, index=True)
    policy_id        = Column(Integer, ForeignKey("policies.id", ondelete="SET NULL"), nullable=True)
    claim_id         = Column(Integer, ForeignKey("claims.id", ondelete="SET NULL"), nullable=True)
    firm_id          = Column(Integer, ForeignKey("broker_firms.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_by_email = Column(String, nullable=False)
    activity_type    = Column(SAEnum(ActivityType, name="activity_type", create_type=False), nullable=False)
    subject          = Column(String, nullable=False)
    body             = Column(String, nullable=True)
    due_date         = Column(Date, nullable=True)
    completed        = Column(Boolean, default=False, nullable=False)
    created_at       = Column(DateTime(timezone=True), nullable=False, index=True)


class ClientToken(Base):
    """Short-lived read-only token a broker shares with a client to view their profile."""
    __tablename__ = "client_tokens"

    id         = Column(Integer, primary_key=True, index=True)
    token      = Column(String(64), unique=True, nullable=False, index=True)
    orgnr      = Column(String(9), nullable=False, index=True)
    label      = Column(String, nullable=True)     # e.g. "Sendt til kontakt 23.03.2026"
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)


class IddBehovsanalyse(Base):
    """IDD-compliant needs assessment (behovsanalyse) per client company."""
    __tablename__ = "idd_behovsanalyse"

    id                         = Column(Integer, primary_key=True, index=True)
    orgnr                      = Column(String(9), nullable=False, index=True)
    firm_id                    = Column(Integer, nullable=False)
    created_by_email           = Column(String, nullable=True)
    created_at                 = Column(DateTime(timezone=True), nullable=False)
    client_name                = Column(String, nullable=True)
    client_contact_name        = Column(String, nullable=True)
    client_contact_email       = Column(String, nullable=True)
    existing_insurance         = Column(JSON, nullable=True)
    risk_appetite              = Column(String, nullable=True)
    property_owned             = Column(Boolean, default=False)
    has_employees              = Column(Boolean, default=False)
    has_vehicles               = Column(Boolean, default=False)
    has_professional_liability = Column(Boolean, default=False)
    has_cyber_risk             = Column(Boolean, default=False)
    annual_revenue_nok         = Column(Float, nullable=True)
    special_requirements       = Column(String, nullable=True)
    recommended_products       = Column(JSON, nullable=True)
    advisor_notes              = Column(String, nullable=True)
    suitability_basis          = Column(String, nullable=True)
    fee_basis                  = Column(String, nullable=True)
    fee_amount_nok             = Column(Float, nullable=True)


class SubmissionStatus(enum.Enum):
    pending   = "pending"
    quoted    = "quoted"
    declined  = "declined"
    withdrawn = "withdrawn"


class Insurer(Base):
    """A known insurance company the broker places business with."""
    __tablename__ = "insurers"

    id            = Column(Integer, primary_key=True, index=True)
    firm_id       = Column(Integer, ForeignKey("broker_firms.id", ondelete="CASCADE"), nullable=False, index=True)
    name          = Column(String, nullable=False)
    org_number    = Column(String(9), nullable=True)
    contact_name  = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)
    contact_phone = Column(String, nullable=True)
    appetite      = Column(JSON, nullable=True)   # ["Eiendom", "Ansvar", "Cyber", ...]
    notes         = Column(String, nullable=True)
    created_at    = Column(DateTime(timezone=True), nullable=False)


class Submission(Base):
    """A market approach — broker approached an insurer on behalf of a client."""
    __tablename__ = "submissions"

    id                  = Column(Integer, primary_key=True, index=True)
    orgnr               = Column(String(9), nullable=False, index=True)
    firm_id             = Column(Integer, ForeignKey("broker_firms.id", ondelete="RESTRICT"), nullable=False, index=True)
    insurer_id          = Column(Integer, ForeignKey("insurers.id", ondelete="CASCADE"), nullable=False, index=True)
    product_type        = Column(String, nullable=False)
    requested_at        = Column(Date, nullable=True)
    status              = Column(SAEnum(SubmissionStatus, name="submission_status", create_type=False), nullable=False, default=SubmissionStatus.pending)
    premium_offered_nok = Column(Float, nullable=True)
    notes               = Column(String, nullable=True)
    created_by_email    = Column(String, nullable=True)
    created_at          = Column(DateTime(timezone=True), nullable=False)


class AuditLog(Base):
    """Immutable audit trail — records key broker actions for compliance and debugging."""
    __tablename__ = "audit_log"

    id          = Column(Integer, primary_key=True, index=True)
    orgnr       = Column(String(9), nullable=True, index=True)
    actor_email = Column(String, nullable=True)
    action      = Column(String, nullable=False)   # e.g. "view_client_profile", "send_tilbud"
    detail      = Column(String, nullable=True)    # JSON-encoded extras
    created_at  = Column(DateTime(timezone=True), nullable=False, index=True)


class JobQueue(Base):
    """Durable background job queue backed by PostgreSQL. Replaces FastAPI BackgroundTasks."""
    __tablename__ = "job_queue"

    id           = Column(Integer, primary_key=True, index=True)
    job_type     = Column(String(100), nullable=False)
    payload      = Column(JSON, nullable=True)
    status       = Column(String(20), nullable=False, default="pending", index=True)
    attempts     = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    created_at   = Column(DateTime(timezone=True), nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    started_at   = Column(DateTime(timezone=True), nullable=True)
    finished_at  = Column(DateTime(timezone=True), nullable=True)
    error        = Column(String, nullable=True)


def init_db():
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
