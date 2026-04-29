"""Dashboard response schemas."""

from typing import List, Optional

from pydantic import BaseModel, Field


class PremiumTrendPoint(BaseModel):
    """One monthly snapshot of the premium book."""

    month: str = Field(
        ..., description="ISO YYYY-MM, marks the month-end snapshot date"
    )
    premium_book: float = Field(
        ..., description="SUM of annual_premium_nok for active policies at month-end"
    )


class PremiumTrendOut(BaseModel):
    """12-month premium-book trend with YoY delta."""

    months: List[PremiumTrendPoint] = Field(
        default_factory=list, description="Oldest-first, 12 entries"
    )
    yoy_delta_pct: Optional[float] = Field(
        None,
        description="Percent change from oldest to newest month; null when oldest is zero",
    )
