"""Portfolio domain models — named company lists for cross-portfolio risk analysis."""

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String

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


class PortfolioRiskSnapshot(Base):
    """Per-company Altman Z'' snapshot scoped to a portfolio.

    One row per (portfolio_id, orgnr, snapshot_at). The risk-summary endpoint
    reads the two most recent distinct snapshot_at values to compute zone
    distribution + transitions.
    """

    __tablename__ = "portfolio_risk_snapshot"

    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(
        Integer, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False
    )
    orgnr = Column(String(9), nullable=False)
    z_score = Column(Float, nullable=True)
    zone = Column(String(16), nullable=True)
    score_20 = Column(Integer, nullable=True)
    snapshot_at = Column(DateTime(timezone=True), nullable=False)
