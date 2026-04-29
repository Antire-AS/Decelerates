"""Admin metrics + service-health endpoints — used by the admin landing page."""

import time
from typing import Optional

import requests
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.models.broker import User, UserRole
from api.dependencies import get_db
from api.schemas.admin import (
    AdminMetricsOut,
    ServiceHealthItem,
    ServicesHealthOut,
)

router = APIRouter()


@router.get("/admin/metrics", response_model=AdminMetricsOut)
def get_admin_metrics(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> AdminMetricsOut:
    """User counts by role + Postgres database size.

    api_calls_24h and ai_tokens_today are stubbed at 0 until request-log
    and token-log tables land in a follow-up.
    """
    total_users = db.query(User).filter(User.firm_id == user.firm_id).count()
    admin_count = (
        db.query(User)
        .filter(User.firm_id == user.firm_id, User.role == UserRole.admin)
        .count()
    )
    broker_count = max(0, total_users - admin_count)

    storage_bytes = (
        db.execute(text("SELECT pg_database_size(current_database())")).scalar() or 0
    )

    return AdminMetricsOut(
        total_users=total_users,
        admin_count=admin_count,
        broker_count=broker_count,
        api_calls_24h=0,
        api_success_pct=None,
        ai_tokens_today=0,
        ai_tokens_budget=None,
        storage_bytes=int(storage_bytes),
        storage_capacity_bytes=None,
    )


def _probe(url: str, timeout: float = 5.0) -> dict:
    """Lightweight HEAD/GET probe; returns {status, latency_ms}."""
    start = time.monotonic()
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True)
        if resp.status_code >= 400:
            resp = requests.get(url, timeout=timeout)
        ms = int((time.monotonic() - start) * 1000)
        if resp.status_code < 400:
            return {"status": "operational", "latency_ms": ms}
        if resp.status_code in (401, 403):
            return {"status": "auth_required", "latency_ms": ms}
        return {"status": "degraded", "latency_ms": ms}
    except Exception:
        return {"status": "down", "latency_ms": None}


_SERVICES: list[tuple[str, str, Optional[str]]] = [
    (
        "https://data.brreg.no/enhetsregisteret/api/enheter/123456789",
        "BRREG Enhetsregisteret",
        None,
    ),
    (
        "https://data.brreg.no/regnskapsregisteret/regnskap/123456789",
        "BRREG Regnskapsregisteret",
        None,
    ),
    ("https://aifoundry.azure.com/", "Azure AI Foundry", None),
    ("https://us-central1-aiplatform.googleapis.com/", "GCP Vertex AI", None),
    ("https://api.opensanctions.org/", "OpenSanctions PEP", None),
    ("https://ws.geonorge.no/adresser/v1/punkt", "Kartverket Geonorge", None),
    ("https://losore.brreg.no/", "Løsøreregisteret", "Krever Maskinporten"),
]


@router.get("/admin/services-health", response_model=ServicesHealthOut)
def get_services_health(
    user: CurrentUser = Depends(get_current_user),
) -> ServicesHealthOut:
    """Probe known external dependencies; cached on the client side via SWR."""
    items = []
    for url, name, note in _SERVICES:
        result = _probe(url)
        items.append(ServiceHealthItem(name=name, note=note, **result))
    return ServicesHealthOut(services=items)
