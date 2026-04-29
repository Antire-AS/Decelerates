"""Admin response schemas."""

from typing import List, Optional

from pydantic import BaseModel, Field


class AdminMetricsOut(BaseModel):
    """Metrics for the admin landing page (mockup 11.03.34)."""

    total_users: int = Field(0, description="Users in the firm")
    admin_count: int = Field(0, description="Subset with role=admin")
    broker_count: int = Field(0, description="Subset with role=broker")
    api_calls_24h: int = Field(
        0, description="HTTP requests served in the last 24h (0 until tracking lands)"
    )
    api_success_pct: Optional[float] = Field(
        None, description="2xx + 3xx share of api_calls_24h"
    )
    ai_tokens_today: int = Field(
        0, description="Foundry tokens consumed today (0 until tracking lands)"
    )
    ai_tokens_budget: Optional[int] = Field(
        None, description="Monthly budget cap if set"
    )
    storage_bytes: int = Field(
        0, description="pg_database_size of the application database"
    )
    storage_capacity_bytes: Optional[int] = Field(
        None, description="Provisioned capacity if known"
    )


class ServiceHealthItem(BaseModel):
    name: str
    status: str = Field(
        ..., description='"operational" | "degraded" | "auth_required" | "down"'
    )
    latency_ms: Optional[int] = None
    note: Optional[str] = None


class ServicesHealthOut(BaseModel):
    services: List[ServiceHealthItem] = Field(default_factory=list)
