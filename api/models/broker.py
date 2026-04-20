"""Broker/User domain models — firms, users, settings, notes, chat memory."""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)

from api.models._base import Base


class BrokerFirm(Base):
    __tablename__ = "broker_firms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    orgnr = Column(String(9), nullable=True)
    azure_tenant_id = Column(String(36), nullable=True, unique=True, index=True)
    is_demo = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)


class UserRole(enum.Enum):
    admin = "admin"
    broker = "broker"
    viewer = "viewer"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    firm_id = Column(
        Integer,
        ForeignKey("broker_firms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    azure_oid = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String, nullable=False)
    name = Column(String, nullable=False)
    role = Column(
        SAEnum(UserRole, name="user_role", create_type=False),
        nullable=False,
        default=UserRole.broker,
    )
    created_at = Column(DateTime(timezone=True), nullable=False)


class BrokerSettings(Base):
    __tablename__ = "broker_settings"

    id = Column(Integer, primary_key=True, default=1)
    firm_name = Column(String, nullable=False, default="")
    orgnr = Column(String(9))
    address = Column(String)
    contact_name = Column(String)
    contact_email = Column(String)
    contact_phone = Column(String)
    updated_at = Column(String)


class BrokerNote(Base):
    __tablename__ = "broker_notes"

    id = Column(Integer, primary_key=True, index=True)
    orgnr = Column(String(9), index=True, nullable=False)
    text = Column(String, nullable=False)
    mentions = Column(JSON, nullable=True)
    created_at = Column(String, nullable=False)


class UserChatMessage(Base):
    """Per-user, per-company chat history.

    Each row is a single turn (user question or assistant answer). Rows are
    grouped on (user_oid, orgnr) to reconstruct a conversation — orgnr is
    NULL for the knowledge-base chat (no company context).
    """

    __tablename__ = "user_chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_oid = Column(String(64), nullable=False, index=True)
    orgnr = Column(String(9), nullable=True, index=True)  # NULL = knowledge chat
    role = Column(String(16), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index(
            "ix_user_chat_messages_user_orgnr_created",
            "user_oid",
            "orgnr",
            "created_at",
        ),
    )


class CompanyWhiteboard(Base):
    """Per-user, per-company focus whiteboard.

    Lightweight workspace where a broker collects key facts from oversikt /
    økonomi / forsikring tabs into one place, plus freeform notes and an
    AI summary. One row per (user_oid, orgnr) — upserts overwrite rather
    than append. Version history is out of scope for MVP.
    """

    __tablename__ = "company_whiteboards"

    id = Column(Integer, primary_key=True, index=True)
    orgnr = Column(String(9), nullable=False, index=True)
    user_oid = Column(String(64), nullable=False, index=True)
    # items: list of {id, label, value, source_tab}
    items = Column(JSON, nullable=False, default=list)
    notes = Column(Text, nullable=True)
    ai_summary = Column(Text, nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_company_whiteboards_orgnr_user", "orgnr", "user_oid", unique=True),
    )
