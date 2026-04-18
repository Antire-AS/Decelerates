"""Portfolio domain models — named company lists for cross-portfolio risk analysis."""

from sqlalchemy import Column, ForeignKey, Integer, String

from api.models._base import Base


class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True, index=True)
    firm_id = Column(
        Integer,
        ForeignKey("broker_firms.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name = Column(String, nullable=False)
    description = Column(String)
    created_at = Column(String, nullable=False)


class PortfolioCompany(Base):
    __tablename__ = "portfolio_companies"

    portfolio_id = Column(
        Integer, ForeignKey("portfolios.id", ondelete="CASCADE"), primary_key=True
    )
    orgnr = Column(String(9), primary_key=True)
    added_at = Column(String, nullable=False)
