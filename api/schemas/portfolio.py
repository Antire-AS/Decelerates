"""Portfolio schemas."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class PortfolioCreate(BaseModel):
    name: str
    description: Optional[str] = ""


class PortfolioAddCompany(BaseModel):
    orgnr: str


class PortfolioBulkAdd(BaseModel):
    orgnrs: List[str]


class PortfolioBulkAddOut(BaseModel):
    added: int
    skipped: int


class ActivityBulkComplete(BaseModel):
    activity_ids: List[int]


class ActivityBulkCompleteOut(BaseModel):
    updated: int


class PortfolioRiskTransition(BaseModel):
    orgnr: str
    navn: Optional[str] = None
    prev_zone: Optional[str] = None
    curr_zone: Optional[str] = None
    prev_z: Optional[float] = None
    curr_z: Optional[float] = None
    delta_z: Optional[float] = None


class PortfolioRiskCompanyRow(BaseModel):
    orgnr: str
    navn: Optional[str] = None
    zone: Optional[str] = None
    z_score: Optional[float] = None
    score_20: Optional[int] = None


class PortfolioRiskSummaryOut(BaseModel):
    portfolio_id: int
    snapshot_at: Optional[str] = None
    prev_snapshot_at: Optional[str] = None
    zones: Dict[str, int] = Field(default_factory=dict)
    transitions: List[PortfolioRiskTransition] = Field(default_factory=list)
    premium_at_risk_nok: float = 0.0
    companies: List[PortfolioRiskCompanyRow] = Field(default_factory=list)


class PortfolioRiskRefreshOut(BaseModel):
    portfolio_id: int
    snapshot_at: str
