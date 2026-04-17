"""Pipeline schemas — stages and deals."""

from datetime import date, datetime
from typing import Literal, Optional
from pydantic import BaseModel

PipelineStageKindLiteral = Literal[
    "lead", "qualified", "quoted", "bound", "won", "lost"
]


class PipelineStageOut(BaseModel):
    id: int
    firm_id: int
    name: str
    kind: PipelineStageKindLiteral
    order_index: int
    color: Optional[str] = None
    created_at: datetime


class PipelineStageCreate(BaseModel):
    name: str
    kind: PipelineStageKindLiteral
    order_index: int = 0
    color: Optional[str] = None


class PipelineStageUpdate(BaseModel):
    name: Optional[str] = None
    order_index: Optional[int] = None
    color: Optional[str] = None


class DealOut(BaseModel):
    id: int
    firm_id: int
    orgnr: str
    stage_id: int
    owner_user_id: Optional[int] = None
    title: Optional[str] = None
    expected_premium_nok: Optional[float] = None
    expected_close_date: Optional[date] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    won_at: Optional[datetime] = None
    lost_at: Optional[datetime] = None
    lost_reason: Optional[str] = None


class DealCreate(BaseModel):
    orgnr: str
    stage_id: int
    owner_user_id: Optional[int] = None
    title: Optional[str] = None
    expected_premium_nok: Optional[float] = None
    expected_close_date: Optional[date] = None
    source: Optional[str] = None
    notes: Optional[str] = None


class DealUpdate(BaseModel):
    title: Optional[str] = None
    owner_user_id: Optional[int] = None
    expected_premium_nok: Optional[float] = None
    expected_close_date: Optional[date] = None
    source: Optional[str] = None
    notes: Optional[str] = None


class DealStageChange(BaseModel):
    stage_id: int


class DealLose(BaseModel):
    reason: Optional[str] = None
