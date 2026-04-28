"""Tender domain models — invitation-to-quote, recipients, and offers."""

import enum

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    JSON,
    LargeBinary,
    String,
    Text,
)

from api.models._base import Base


class TenderStatus(enum.Enum):
    draft = "draft"
    sent = "sent"
    closed = "closed"
    analysed = "analysed"


class Tender(Base):
    __tablename__ = "tenders"

    id = Column(Integer, primary_key=True, index=True)
    orgnr = Column(String(9), nullable=False, index=True)
    firm_id = Column(
        Integer,
        ForeignKey("broker_firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_email = Column(String, nullable=True)
    title = Column(String, nullable=False)
    product_types = Column(JSON, nullable=False)
    deadline = Column(Date, nullable=True)
    notes = Column(String, nullable=True)
    status = Column(
        SAEnum(TenderStatus, name="tender_status", create_type=False),
        nullable=False,
        default=TenderStatus.draft,
    )
    analysis_result = Column(JSON, nullable=True)
    # ID returned by the e-sign provider when the broker sends the contract
    # for signature. The provider's webhook carries the same ID, so this is
    # how we route callbacks back to the tender row. Partial unique index
    # (WHERE NOT NULL) is created by the Alembic migration, not here — the
    # model field stays simple so it doesn't clash with the partial index.
    contract_session_id = Column(String(128), nullable=True)
    # Customer-facing portal — broker generates the token after running the
    # AI analysis. Customer opens /portal/tender/<token>, reviews, approves
    # or rejects. Approval kicks off the existing DocuSeal flow via
    # `contract_session_id` above. See migration `p4q5r6s7t8u9` for the
    # partial unique index on customer_access_token.
    customer_access_token = Column(String(64), nullable=True)
    customer_email = Column(String, nullable=True)
    customer_approval_status = Column(String(16), nullable=True)
    customer_approval_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)


class TenderRecipientStatus(enum.Enum):
    pending = "pending"
    sent = "sent"
    received = "received"
    declined = "declined"


class TenderDeclineReason(enum.Enum):
    """Why an insurer declined to quote on a tender. Free-string-backed
    so we can grow the vocabulary without an enum migration; the Python
    enum constrains the writeable values."""

    capacity = "capacity"
    bad_match = "bad_match"
    high_risk = "high_risk"
    other = "other"


class TenderRecipient(Base):
    __tablename__ = "tender_recipients"

    id = Column(Integer, primary_key=True, index=True)
    tender_id = Column(
        Integer,
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    insurer_name = Column(String, nullable=False)
    insurer_email = Column(String, nullable=True)
    # Long-lived URL-safe token — lets the insurer upload their quote on
    # /anbud/respond/<token> without needing a broker-side login.
    access_token = Column(String(64), nullable=True, unique=True)
    status = Column(
        SAEnum(
            TenderRecipientStatus, name="tender_recipient_status", create_type=False
        ),
        nullable=False,
        default=TenderRecipientStatus.pending,
    )
    sent_at = Column(DateTime(timezone=True), nullable=True)
    response_at = Column(DateTime(timezone=True), nullable=True)
    decline_reason = Column(String(32), nullable=True)
    decline_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)


class TenderOffer(Base):
    __tablename__ = "tender_offers"

    id = Column(Integer, primary_key=True, index=True)
    tender_id = Column(
        Integer,
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recipient_id = Column(
        Integer,
        ForeignKey("tender_recipients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    insurer_name = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    pdf_content = Column(LargeBinary, nullable=False)
    extracted_text = Column(String, nullable=True)
    extracted_data = Column(JSON, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), nullable=False)
