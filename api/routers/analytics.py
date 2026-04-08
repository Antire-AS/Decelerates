"""Analytics endpoints — premium book aggregations."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
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
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Aggregate the broker's premium book by insurer, product type, and status."""
    firm_id = user.firm_id
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


def _fmt_commission_bucket(bucket: dict, key_name: str, total_commission: float) -> list:
    total = total_commission or 1
    return sorted(
        [{key_name: k, **v,
          "avg_rate_pct": round(v["commission"] / v["premium"] * 100, 1) if v["premium"] else 0,
          "share_pct": round(v["commission"] / total * 100, 1)}
         for k, v in bucket.items()],
        key=lambda x: x["commission"], reverse=True,
    )


@router.get("/analytics/commissions")
def get_commission_analytics(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Aggregate commission income from the broker's policy book."""
    policies = db.query(Policy).filter(
        Policy.firm_id == user.firm_id,
        Policy.status == PolicyStatus.active,
    ).all()

    total_commission = 0.0
    by_product: dict[str, dict] = {}
    by_insurer: dict[str, dict] = {}

    for p in policies:
        # Prefer stored amount; fall back to rate × premium
        comm = p.commission_amount_nok
        if comm is None and p.commission_rate_pct is not None and p.annual_premium_nok:
            comm = p.annual_premium_nok * p.commission_rate_pct / 100
        if comm is None:
            comm = 0.0
        total_commission += comm

        for bucket, key in [(by_product, p.product_type or "Ukjent"),
                            (by_insurer, p.insurer or "Ukjent")]:
            if key not in bucket:
                bucket[key] = {"count": 0, "commission": 0.0, "premium": 0.0}
            bucket[key]["count"] += 1
            bucket[key]["commission"] += comm
            bucket[key]["premium"] += p.annual_premium_nok or 0.0

    return {
        "total_commission_nok": round(total_commission),
        "policy_count": len(policies),
        "by_product": _fmt_commission_bucket(by_product, "product_type", total_commission),
        "by_insurer": _fmt_commission_bucket(by_insurer, "insurer", total_commission),
    }
