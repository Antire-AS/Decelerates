"""Analytics endpoints — premium book aggregations."""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_optional_user
from api.db import Policy, PolicyStatus
from api.dependencies import get_db

router = APIRouter()


def _aggregate(policies: list, key: str) -> list:
    """Group policies by a string field; return sorted list of {key, count, total_premium, share_pct}."""
    buckets: dict[str, dict] = {}
    for p in policies:
        val = getattr(p, key) or "Ukjent"
        val = val.value if hasattr(val, "value") else str(val)
        if val not in buckets:
            buckets[val] = {"count": 0, "total_premium": 0.0}
        buckets[val]["count"] += 1
        buckets[val]["total_premium"] += p.annual_premium_nok or 0.0
    total = sum(b["total_premium"] for b in buckets.values()) or 1
    return sorted(
        [{key: k, **v, "share_pct": round(v["total_premium"] / total * 100, 1)}
         for k, v in buckets.items()],
        key=lambda x: x["total_premium"],
        reverse=True,
    )


@router.get("/analytics/premiums")
def get_premium_analytics(
    db: Session = Depends(get_db),
    user: Optional[CurrentUser] = Depends(get_optional_user),
) -> dict:
    """Aggregate the broker's premium book by insurer, product type, and status."""
    firm_id = user.firm_id if user else 1
    all_policies = db.query(Policy).filter(Policy.firm_id == firm_id).all()
    active = [p for p in all_policies if p.status == PolicyStatus.active]
    total_book = sum(p.annual_premium_nok or 0.0 for p in active)
    today = date.today()
    renewals_90d = sum(
        p.annual_premium_nok or 0.0
        for p in active
        if p.renewal_date and today <= p.renewal_date <= today + timedelta(days=90)
    )
    avg_premium = total_book / len(active) if active else 0.0
    return {
        "total_premium_book": round(total_book),
        "active_policy_count": len(active),
        "renewals_90d_premium": round(renewals_90d),
        "avg_premium_per_policy": round(avg_premium),
        "by_insurer": _aggregate(active, "insurer"),
        "by_product": _aggregate(active, "product_type"),
        "by_status": _aggregate(all_policies, "status"),
    }
