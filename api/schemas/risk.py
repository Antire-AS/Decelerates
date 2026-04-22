"""Risk schemas."""

from typing import List, Optional
from pydantic import BaseModel, Field


class RiskOfferRecommendation(BaseModel):
    type: Optional[str] = None
    anbefalt_sum: Optional[str] = None
    prioritet: Optional[str] = None
    begrunnelse: Optional[str] = None
    estimert_premie: Optional[str] = None


class RiskOfferOut(BaseModel):
    orgnr: str
    navn: Optional[str] = None
    risk_score: Optional[int] = None
    risk_factors: List[str] = Field(default_factory=list)
    sammendrag: Optional[str] = None
    anbefalinger: List[RiskOfferRecommendation] = Field(default_factory=list)
    total_premieanslag: Optional[str] = None


class NarrativeOut(BaseModel):
    orgnr: str
    narrative: str


class AltmanTrendPoint(BaseModel):
    year: int
    z_score: float
    zone: str
    score_20: int


class AltmanHistoryOut(BaseModel):
    orgnr: str
    points: List[AltmanTrendPoint] = Field(default_factory=list)
