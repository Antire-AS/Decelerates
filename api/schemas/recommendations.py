"""Recommendation schemas for the dashboard panel."""

from typing import List, Optional

from pydantic import BaseModel, Field


class RecommendationOut(BaseModel):
    kind: str = Field(..., description='"pep" | "stale_narrative" | "peer_overage"')
    orgnr: Optional[str] = None
    headline: str
    body: str
    cta_label: str
    cta_href: str


class DashboardRecommendationsOut(BaseModel):
    items: List[RecommendationOut] = Field(default_factory=list)
