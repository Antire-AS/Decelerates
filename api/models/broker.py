"""Broker/User domain models — firms, users, settings, notes."""

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
