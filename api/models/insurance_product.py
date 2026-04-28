"""Insurance product catalog — drives tender creation, IDD, and recommendations."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)

from api.models._base import Base


class InsuranceProduct(Base):
    __tablename__ = "insurance_products"
    __table_args__ = (
        UniqueConstraint("category", "sub_category", "name", name="uq_product_triple"),
    )

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(64), nullable=False, index=True)
    sub_category = Column(String(64), nullable=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    typical_coverage_limits = Column(JSON, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
