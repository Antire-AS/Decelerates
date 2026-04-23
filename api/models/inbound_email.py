"""Inbound email model — audit log of ACS Event Grid deliveries.

Every webhook invocation writes one row here (matched, orphaned, or
error). The PDF attachment bytes, when ingested as offers, land in
`tender_offers` via TenderService.upload_offer; we just store the link
as `offer_id` so the two tables stay reconcilable.
"""

from sqlalchemy import Column, DateTime, Index, Integer, String, Text, text

from api.models._base import Base


class IncomingEmailLog(Base):
    __tablename__ = "incoming_email_log"

    id = Column(Integer, primary_key=True, index=True)
    received_at = Column(DateTime(timezone=True), nullable=False)
    sender = Column(String(320), nullable=True)
    recipient = Column(String(320), nullable=True)
    subject = Column(Text, nullable=True)
    tender_ref = Column(String(64), nullable=True)
    tender_id = Column(Integer, nullable=True)
    recipient_id = Column(Integer, nullable=True)
    status = Column(String(32), nullable=False)  # matched | orphaned | error | dedup
    error_message = Column(Text, nullable=True)
    attachment_count = Column(Integer, nullable=False, default=0)
    offer_id = Column(Integer, nullable=True)
    # RFC822 Message-ID — used to dedup replayed webhook deliveries. Nullable
    # because ACS rows don't always carry one; partial unique index enforces
    # dedup only when it's set. See migration d1e2f3g4h5i6.
    message_id = Column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_incoming_email_log_message_id_unique",
            "message_id",
            unique=True,
            postgresql_where=text("message_id IS NOT NULL"),
        ),
    )
