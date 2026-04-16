"""Insurance domain models — offers, documents, insurers, submissions, recommendations."""
import enum

from sqlalchemy import (
    Column, Date, DateTime, Enum as SAEnum, Float, ForeignKey,
    Integer, JSON, LargeBinary, String,
)

from api.models._base import Base


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
    insurer_name   = Column(String)
    uploaded_at    = Column(String, nullable=False)
    pdf_content    = Column(LargeBinary, nullable=False)
    extracted_text = Column(String)
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
    category       = Column(String)
    insurer        = Column(String)
    year           = Column(Integer)
    period         = Column(String)
    orgnr          = Column(String(9))
    filename       = Column(String, nullable=False)
    pdf_content    = Column(LargeBinary, nullable=False)
    extracted_text = Column(String)
    uploaded_at    = Column(String, nullable=False)
    tags           = Column(String, nullable=True)
    cached_keypoints      = Column(JSON, nullable=True)
    parsed_premium_nok    = Column(Float, nullable=True)
    parsed_coverage_nok   = Column(Float, nullable=True)
    parsed_deductible_nok = Column(Float, nullable=True)
    auto_comparison_result = Column(JSON, nullable=True)


class SubmissionStatus(enum.Enum):
    pending   = "pending"
    quoted    = "quoted"
    declined  = "declined"
    withdrawn = "withdrawn"


class Insurer(Base):
    __tablename__ = "insurers"

    id            = Column(Integer, primary_key=True, index=True)
    firm_id       = Column(Integer, ForeignKey("broker_firms.id", ondelete="CASCADE"), nullable=False, index=True)
    name          = Column(String, nullable=False)
    org_number    = Column(String(9), nullable=True)
    contact_name  = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)
    contact_phone = Column(String, nullable=True)
    appetite      = Column(JSON, nullable=True)
    notes         = Column(String, nullable=True)
    api_key       = Column(String(64), nullable=True, unique=True, index=True)
    created_at    = Column(DateTime(timezone=True), nullable=False)


class Submission(Base):
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
    __tablename__ = "recommendations"

    id                  = Column(Integer, primary_key=True, index=True)
    orgnr               = Column(String(9), nullable=False, index=True)
    firm_id             = Column(Integer, ForeignKey("broker_firms.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_by_email    = Column(String, nullable=True)
    created_at          = Column(DateTime(timezone=True), nullable=False)
    idd_id              = Column(Integer, ForeignKey("idd_behovsanalyse.id", ondelete="SET NULL"), nullable=True)
    submission_ids      = Column(JSON, nullable=True)
    recommended_insurer = Column(String, nullable=True)
    rationale_text      = Column(String, nullable=True)
    pdf_content         = Column(LargeBinary, nullable=True)
    signing_session_id  = Column(String, nullable=True, index=True)
    signed_at           = Column(DateTime(timezone=True), nullable=True)
    signed_pdf_blob_url = Column(String, nullable=True)
