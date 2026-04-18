"""System domain models — job queue, notifications, saved searches."""

import enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    JSON,
    String,
)

from api.models._base import Base


class JobQueue(Base):
    __tablename__ = "job_queue"

    id = Column(Integer, primary_key=True, index=True)
    job_type = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    created_at = Column(DateTime(timezone=True), nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    error = Column(String, nullable=True)


class NotificationKind(enum.Enum):
    renewal = "renewal"
    activity_overdue = "activity_overdue"
    mention = "mention"
    claim_new = "claim_new"
    deal_won = "deal_won"
    coverage_gap = "coverage_gap"
    digest = "digest"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    firm_id = Column(
        Integer,
        ForeignKey("broker_firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    orgnr = Column(String(9), nullable=True, index=True)
    kind = Column(
        SAEnum(NotificationKind, name="notification_kind", create_type=False),
        nullable=False,
    )
    title = Column(String, nullable=False)
    message = Column(String, nullable=True)
    link = Column(String, nullable=True)
    read = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False)


class SavedSearch(Base):
    __tablename__ = "saved_searches"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String, nullable=False)
    params = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
