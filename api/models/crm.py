"""CRM domain models — contacts, policies, claims, activities, client tokens."""
import enum

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum as SAEnum, Float,
    ForeignKey, Integer, String,
)

from api.models._base import Base


class ContactPerson(Base):
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
    __tablename__ = "activities"

    id                  = Column(Integer, primary_key=True, index=True)
    orgnr               = Column(String(9), nullable=True, index=True)
    policy_id           = Column(Integer, ForeignKey("policies.id", ondelete="SET NULL"), nullable=True)
    claim_id            = Column(Integer, ForeignKey("claims.id", ondelete="SET NULL"), nullable=True)
    firm_id             = Column(Integer, ForeignKey("broker_firms.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_by_email    = Column(String, nullable=False)
    assigned_to_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    activity_type       = Column(SAEnum(ActivityType, name="activity_type", create_type=False), nullable=False)
    subject             = Column(String, nullable=False)
    body                = Column(String, nullable=True)
    due_date            = Column(Date, nullable=True, index=True)
    completed           = Column(Boolean, default=False, nullable=False, index=True)
    created_at          = Column(DateTime(timezone=True), nullable=False, index=True)


class ClientToken(Base):
    __tablename__ = "client_tokens"

    id         = Column(Integer, primary_key=True, index=True)
    token      = Column(String(64), unique=True, nullable=False, index=True)
    orgnr      = Column(String(9), nullable=False, index=True)
    label      = Column(String, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
