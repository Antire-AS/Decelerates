"""Pipeline domain models — deal stages and opportunities."""

import enum

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)

from api.models._base import Base


class PipelineStageKind(enum.Enum):
    lead = "lead"
    qualified = "qualified"
    quoted = "quoted"
    bound = "bound"
    won = "won"
    lost = "lost"


class PipelineStage(Base):
    __tablename__ = "pipeline_stages"

    id = Column(Integer, primary_key=True, index=True)
    firm_id = Column(
        Integer,
        ForeignKey("broker_firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String, nullable=False)
    kind = Column(
        SAEnum(PipelineStageKind, name="pipeline_stage_kind", create_type=False),
        nullable=False,
    )
    order_index = Column(Integer, nullable=False, default=0)
    color = Column(String(7), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("firm_id", "name", name="uq_pipeline_stage_firm_name"),
    )


class Deal(Base):
    __tablename__ = "deals"

    id = Column(Integer, primary_key=True, index=True)
    firm_id = Column(
        Integer,
        ForeignKey("broker_firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    orgnr = Column(String(9), nullable=False, index=True)
    stage_id = Column(
        Integer,
        ForeignKey("pipeline_stages.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    owner_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title = Column(String, nullable=True)
    expected_premium_nok = Column(Float, nullable=True)
    expected_close_date = Column(Date, nullable=True, index=True)
    source = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    won_at = Column(DateTime(timezone=True), nullable=True)
    lost_at = Column(DateTime(timezone=True), nullable=True)
    lost_reason = Column(String, nullable=True)
