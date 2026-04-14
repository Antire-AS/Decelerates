import enum
import os
from sqlalchemy import (
    Boolean, create_engine, Column, Date, DateTime, Enum as SAEnum,
    Integer, String, Float, JSON, LargeBinary, text, UniqueConstraint, ForeignKey,
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
    # Auto-analysis fields (populated by background doc-intelligence agent)
    cached_keypoints      = Column(JSON, nullable=True)
    parsed_premium_nok    = Column(Float, nullable=True)
    parsed_coverage_nok   = Column(Float, nullable=True)
    parsed_deductible_nok = Column(Float, nullable=True)
    auto_comparison_result = Column(JSON, nullable=True)


class BrokerNote(Base):
    __tablename__ = "broker_notes"

    id         = Column(Integer, primary_key=True, index=True)
    orgnr      = Column(String(9), index=True, nullable=False)
    text       = Column(String, nullable=False)
    # Plan §🟢 #14 — list of email strings extracted from @mentions in `text`.
    # Stored (rather than re-parsed on every read) so the notification fan-out
    # only fires once per save and tests can assert against the persisted shape.
    mentions   = Column(JSON, nullable=True)
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
    is_demo    = Column(Boolean, default=False, nullable=False)
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
    status              = Column(SAEnum(PolicyStatus, name="policy_status", create_type=False), nullable=False, default=PolicyStatus.active, index=True)
    renewal_stage       = Column(SAEnum(RenewalStage, name="renewal_stage", create_type=False), nullable=False, default=RenewalStage.not_started)
    notes               = Column(String, nullable=True)
    document_url        = Column(String, nullable=True)
    last_renewal_notified_days = Column(Integer, nullable=True)
    commission_rate_pct = Column(Float, nullable=True)
    commission_amount_nok = Column(Float, nullable=True)
    renewal_brief       = Column(String, nullable=True)
    renewal_email_draft = Column(String, nullable=True)
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

    id                  = Column(Integer, primary_key=True, index=True)
    orgnr               = Column(String(9), nullable=True, index=True)
    policy_id           = Column(Integer, ForeignKey("policies.id", ondelete="SET NULL"), nullable=True)
    claim_id            = Column(Integer, ForeignKey("claims.id", ondelete="SET NULL"), nullable=True)
    firm_id             = Column(Integer, ForeignKey("broker_firms.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_by_email    = Column(String, nullable=False)
    # Plan §🟢 #14 — multi-user assignment. Nullable so legacy rows + unassigned
    # tasks remain valid; SET NULL on user delete so we don't orphan tasks.
    assigned_to_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    activity_type       = Column(SAEnum(ActivityType, name="activity_type", create_type=False), nullable=False)
    subject             = Column(String, nullable=False)
    body                = Column(String, nullable=True)
    due_date            = Column(Date, nullable=True, index=True)
    completed           = Column(Boolean, default=False, nullable=False, index=True)
    created_at          = Column(DateTime(timezone=True), nullable=False, index=True)


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


class Recommendation(Base):
    """A formal recommendation letter — broker's advised insurer(s) for a client."""
    __tablename__ = "recommendations"

    id                  = Column(Integer, primary_key=True, index=True)
    orgnr               = Column(String(9), nullable=False, index=True)
    firm_id             = Column(Integer, ForeignKey("broker_firms.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_by_email    = Column(String, nullable=True)
    created_at          = Column(DateTime(timezone=True), nullable=False)
    idd_id              = Column(Integer, ForeignKey("idd_behovsanalyse.id", ondelete="SET NULL"), nullable=True)
    submission_ids      = Column(JSON, nullable=True)       # [int, ...]
    recommended_insurer = Column(String, nullable=True)     # name of recommended insurer
    rationale_text      = Column(String, nullable=True)     # LLM-generated rationale
    pdf_content         = Column(LargeBinary, nullable=True)
    # Plan §🟢 #11 — Signicat e-sign tracking. All nullable so existing rows
    # remain valid; the workflow is opt-in via POST /recommendations/{id}/sign.
    signing_session_id  = Column(String, nullable=True, index=True)
    signed_at           = Column(DateTime(timezone=True), nullable=True)
    signed_pdf_blob_url = Column(String, nullable=True)


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


class LawfulBasis(enum.Enum):
    consent               = "consent"
    legitimate_interest   = "legitimate_interest"
    contract              = "contract"
    legal_obligation      = "legal_obligation"


class ConsentRecord(Base):
    """GDPR consent and lawful-basis records per client company."""
    __tablename__ = "consent_records"

    id                = Column(Integer, primary_key=True, index=True)
    orgnr             = Column(String(9), nullable=False, index=True)
    firm_id           = Column(Integer, ForeignKey("broker_firms.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at        = Column(DateTime(timezone=True), nullable=False)
    lawful_basis      = Column(SAEnum(LawfulBasis, name="lawful_basis", create_type=False), nullable=False)
    purpose           = Column(String, nullable=False)   # "insurance_advice" | "credit_check" | "marketing"
    captured_by_email = Column(String, nullable=False)
    withdrawn_at      = Column(DateTime(timezone=True), nullable=True)
    withdrawal_reason = Column(String, nullable=True)


class NotificationKind(enum.Enum):
    """Locked semantic kind for in-app notifications. Drives the icon and
    routing in the bell-icon dropdown. Add new kinds here when a new event
    type starts firing notifications — frontend defaults to a generic icon."""
    renewal          = "renewal"
    activity_overdue = "activity_overdue"
    mention          = "mention"
    claim_new        = "claim_new"
    deal_won         = "deal_won"
    coverage_gap     = "coverage_gap"
    digest           = "digest"


class Notification(Base):
    """In-app notification. One row per (user, event) — i.e. a renewal alert
    sent to 3 users in the same firm produces 3 rows. Cron jobs that send
    emails ALSO write Notifications so the bell-icon panel mirrors the same
    events without requiring an inbox-zero email habit. Plan §🟢 #17."""
    __tablename__ = "notifications"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    firm_id     = Column(Integer, ForeignKey("broker_firms.id", ondelete="CASCADE"), nullable=False, index=True)
    orgnr       = Column(String(9), nullable=True, index=True)
    kind        = Column(SAEnum(NotificationKind, name="notification_kind", create_type=False), nullable=False)
    title       = Column(String, nullable=False)
    message     = Column(String, nullable=True)
    link        = Column(String, nullable=True)        # frontend route to navigate to on click
    read        = Column(Boolean, default=False, nullable=False, index=True)
    created_at  = Column(DateTime(timezone=True), nullable=False)


class PipelineStageKind(enum.Enum):
    """Locked semantic role for a pipeline stage. The display `name` is
    customizable per firm, but the `kind` is fixed so analytics, reports, and
    cron jobs can reason about stage semantics regardless of broker rebranding.
    """
    lead      = "lead"
    qualified = "qualified"
    quoted    = "quoted"
    bound     = "bound"
    won       = "won"
    lost      = "lost"


class PipelineStage(Base):
    """A column in a broker firm's deal pipeline. Per-firm so each broker
    can name and order their own funnel — but `kind` is the locked semantic
    role for analytics."""
    __tablename__ = "pipeline_stages"

    id          = Column(Integer, primary_key=True, index=True)
    firm_id     = Column(Integer, ForeignKey("broker_firms.id", ondelete="CASCADE"), nullable=False, index=True)
    name        = Column(String, nullable=False)        # display label, e.g. "Tilbud sendt"
    kind        = Column(SAEnum(PipelineStageKind, name="pipeline_stage_kind", create_type=False), nullable=False)
    order_index = Column(Integer, nullable=False, default=0)
    color       = Column(String(7), nullable=True)      # hex like "#4A6FA5", optional
    created_at  = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("firm_id", "name", name="uq_pipeline_stage_firm_name"),
    )


class Deal(Base):
    """An open opportunity moving through the broker firm's pipeline.

    A Deal is firm-scoped and points at a specific company (orgnr). The
    stage_id reference is RESTRICT so we can't accidentally orphan deals
    by deleting stages — admins must reassign first.
    """
    __tablename__ = "deals"

    id                   = Column(Integer, primary_key=True, index=True)
    firm_id              = Column(Integer, ForeignKey("broker_firms.id", ondelete="CASCADE"), nullable=False, index=True)
    orgnr                = Column(String(9), nullable=False, index=True)
    stage_id             = Column(Integer, ForeignKey("pipeline_stages.id", ondelete="RESTRICT"), nullable=False, index=True)
    owner_user_id        = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    title                = Column(String, nullable=True)
    expected_premium_nok = Column(Float, nullable=True)
    expected_close_date  = Column(Date, nullable=True, index=True)
    source               = Column(String, nullable=True)   # "Inbound", "Outbound", "Referral", …
    notes                = Column(String, nullable=True)
    created_at           = Column(DateTime(timezone=True), nullable=False)
    updated_at           = Column(DateTime(timezone=True), nullable=False)
    won_at               = Column(DateTime(timezone=True), nullable=True)
    lost_at              = Column(DateTime(timezone=True), nullable=True)
    lost_reason          = Column(String, nullable=True)


class SavedSearch(Base):
    """A user-saved /prospecting filter set. Per-user (not per-firm) so each
    broker can curate their own. Plan §🟢 #19."""
    __tablename__ = "saved_searches"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name       = Column(String, nullable=False)
    params     = Column(JSON, nullable=False)   # arbitrary filter dict
    created_at = Column(DateTime(timezone=True), nullable=False)


def init_db():
    with engine.connect() as conn:
        # Check first, then create — `CREATE EXTENSION IF NOT EXISTS` still
        # runs the privilege check even when the extension already exists,
        # which fails for non-superuser app roles (e.g. broker_prod /
        # broker_staging) on Azure Postgres because pgvector is "untrusted"
        # there. Skip the call entirely if the extension is already installed.
        existing = conn.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        ).scalar()
        if not existing:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
    Base.metadata.create_all(bind=engine)
