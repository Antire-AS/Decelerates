"""News domain model — headlines fetched from Serper /news, flagged for
materiality by Foundry gpt-5.4-mini."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from api.models._base import Base


class CompanyNews(Base):
    __tablename__ = "company_news"
    __table_args__ = (
        UniqueConstraint("orgnr", "url", name="uq_company_news_orgnr_url"),
    )

    id = Column(Integer, primary_key=True, index=True)
    orgnr = Column(String(9), nullable=False)
    headline = Column(Text, nullable=False)
    url = Column(Text, nullable=False)
    source = Column(String(255), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    snippet = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    material = Column(Boolean, nullable=False, default=False)
    event_type = Column(String(32), nullable=True)
    fetched_at = Column(DateTime(timezone=True), nullable=False)
