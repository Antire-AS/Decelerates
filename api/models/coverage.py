"""Coverage analysis model — AI-parsed coverage breakdown of insurance policies."""

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    LargeBinary,
    String,
)

from api.models._base import Base


class CoverageAnalysis(Base):
    __tablename__ = "coverage_analyses"

    id = Column(Integer, primary_key=True, index=True)
    orgnr = Column(String(9), nullable=False, index=True)
    firm_id = Column(
        Integer,
        ForeignKey("broker_firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id = Column(
        Integer,
        ForeignKey("insurance_documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title = Column(String, nullable=False)
    insurer = Column(String, nullable=True)
    product_type = Column(String, nullable=True)
    filename = Column(String, nullable=True)
    pdf_content = Column(LargeBinary, nullable=True)
    extracted_text = Column(String, nullable=True)
    coverage_data = Column(JSON, nullable=True)
    premium_nok = Column(Float, nullable=True)
    deductible_nok = Column(Float, nullable=True)
    coverage_sum_nok = Column(Float, nullable=True)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), nullable=False)
