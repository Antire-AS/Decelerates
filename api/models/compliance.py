"""Compliance domain models — SLA agreements, IDD analyses, GDPR consent, audit log."""
import enum

from sqlalchemy import (
    Column, DateTime, Enum as SAEnum, Float, ForeignKey,
    Integer, JSON, LargeBinary, String, Boolean,
)

from api.models._base import Base


class SlaAgreement(Base):
    __tablename__ = "sla_agreements"

    id              = Column(Integer, primary_key=True)
    created_at      = Column(String, nullable=False)
    broker_snapshot = Column(JSON)
    client_orgnr    = Column(String(9), index=True)
    client_navn     = Column(String)
    client_adresse  = Column(String)
    client_kontakt  = Column(String)
    start_date      = Column(String)
    account_manager = Column(String)
    insurance_lines = Column(JSON)
    fee_structure   = Column(JSON)
    status          = Column(String, default="draft")
    form_data       = Column(JSON)
    signed_at       = Column(DateTime(timezone=True), nullable=True)
    signed_by       = Column(String, nullable=True)


class IddBehovsanalyse(Base):
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


class LawfulBasis(enum.Enum):
    consent               = "consent"
    legitimate_interest   = "legitimate_interest"
    contract              = "contract"
    legal_obligation      = "legal_obligation"


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id                = Column(Integer, primary_key=True, index=True)
    orgnr             = Column(String(9), nullable=False, index=True)
    firm_id           = Column(Integer, ForeignKey("broker_firms.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at        = Column(DateTime(timezone=True), nullable=False)
    lawful_basis      = Column(SAEnum(LawfulBasis, name="lawful_basis", create_type=False), nullable=False)
    purpose           = Column(String, nullable=False)
    captured_by_email = Column(String, nullable=False)
    withdrawn_at      = Column(DateTime(timezone=True), nullable=True)
    withdrawal_reason = Column(String, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id          = Column(Integer, primary_key=True, index=True)
    orgnr       = Column(String(9), nullable=True, index=True)
    actor_email = Column(String, nullable=True)
    action      = Column(String, nullable=False)
    detail      = Column(String, nullable=True)
    created_at  = Column(DateTime(timezone=True), nullable=False, index=True)
