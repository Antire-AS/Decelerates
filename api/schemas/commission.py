"""Commission schemas."""

from typing import List, Optional
from pydantic import BaseModel


class PolicyCommissionOut(BaseModel):
    id: int
    policy_number: Optional[str] = None
    product_type: str
    insurer: str
    status: str
    annual_premium_nok: Optional[float] = None
    commission_rate_pct: Optional[float] = None
    commission_amount_nok: float


class CommissionSummaryOut(BaseModel):
    total_commission_ytd: float
    total_premium_managed: float
    active_policy_count: int
    revenue_by_product_type: dict
    revenue_by_insurer: dict
    renewal_commission_vs_new: dict


class CommissionClientOut(BaseModel):
    orgnr: str
    total_commission_lifetime: float
    total_commission_ytd: float
    policies: List[PolicyCommissionOut]


class PolicyMissingOut(BaseModel):
    id: int
    orgnr: str
    policy_number: Optional[str] = None
    product_type: str
    insurer: str
    annual_premium_nok: Optional[float] = None
    renewal_date: Optional[str] = None


class CommissionProjectionBucket(BaseModel):
    period: str
    expected_commission: float
    policy_count: int


class CommissionProjectionsOut(BaseModel):
    buckets: List[CommissionProjectionBucket]
    months_ahead: int
