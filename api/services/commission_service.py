"""Commission and revenue tracking service."""
from datetime import date, datetime, timedelta, timezone
from typing import List

from sqlalchemy.orm import Session

from api.db import Policy, PolicyStatus
import logging

logger = logging.getLogger(__name__)



def _calc_policy_commission(p: Policy) -> float:
    """Return effective commission for a policy (amount takes precedence over rate)."""
    comm = p.commission_amount_nok or 0.0
    if comm == 0.0 and p.commission_rate_pct and p.annual_premium_nok:
        comm = p.annual_premium_nok * p.commission_rate_pct / 100.0
    return comm


def _is_renewal_policy(p: Policy, now: datetime) -> bool:
    """A policy is a renewal if it is more than 12 months old."""
    if not p.created_at:
        return False
    return (now.date() - p.created_at.date()).days > 365


class CommissionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_commission_summary(self, firm_id: int) -> dict:
        """Aggregate commission metrics for the broker firm."""
        policies = (
            self.db.query(Policy)
            .filter(Policy.firm_id == firm_id)
            .all()
        )
        now = datetime.now(timezone.utc)
        ytd_total = premium_managed = new_comm = renewal_comm = 0.0
        active_count = 0
        by_product: dict[str, float] = {}
        by_insurer: dict[str, float] = {}
        for p in policies:
            if p.status != PolicyStatus.active:
                continue
            active_count += 1
            premium_managed += p.annual_premium_nok or 0.0
            comm = _calc_policy_commission(p)
            if p.created_at and p.created_at.year == now.year:
                ytd_total += comm
            by_product[p.product_type] = by_product.get(p.product_type, 0.0) + comm
            by_insurer[p.insurer] = by_insurer.get(p.insurer, 0.0) + comm
            if _is_renewal_policy(p, now):
                renewal_comm += comm
            else:
                new_comm += comm

        return {
            "total_commission_ytd":    round(ytd_total, 2),
            "total_premium_managed":   round(premium_managed, 2),
            "active_policy_count":     active_count,
            "revenue_by_product_type": {k: round(v, 2) for k, v in by_product.items()},
            "revenue_by_insurer":      {k: round(v, 2) for k, v in by_insurer.items()},
            "renewal_commission_vs_new": {
                "new":     round(new_comm, 2),
                "renewal": round(renewal_comm, 2),
            },
        }

    def get_commission_by_client(self, firm_id: int, orgnr: str) -> dict:
        """Commission and premium breakdown for a single client."""
        now = datetime.now(timezone.utc)
        policies = (
            self.db.query(Policy)
            .filter(Policy.firm_id == firm_id, Policy.orgnr == orgnr)
            .all()
        )
        total_lifetime = 0.0
        total_ytd = 0.0
        policy_list = []

        for p in policies:
            comm = _calc_policy_commission(p)
            total_lifetime += comm
            if p.created_at and p.created_at.year == now.year:
                total_ytd += comm
            policy_list.append({
                "id":                  p.id,
                "policy_number":       p.policy_number,
                "product_type":        p.product_type,
                "insurer":             p.insurer,
                "status":              p.status.value,
                "annual_premium_nok":  p.annual_premium_nok,
                "commission_rate_pct": p.commission_rate_pct,
                "commission_amount_nok": round(comm, 2),
            })

        return {
            "orgnr":                  orgnr,
            "total_commission_lifetime": round(total_lifetime, 2),
            "total_commission_ytd":   round(total_ytd, 2),
            "policies":               policy_list,
        }

    def list_policies_missing_commission(self, firm_id: int) -> list[Policy]:
        """Active policies with no commission rate or amount recorded."""
        return (
            self.db.query(Policy)
            .filter(
                Policy.firm_id == firm_id,
                Policy.status == PolicyStatus.active,
                Policy.commission_rate_pct.is_(None),
                Policy.commission_amount_nok.is_(None),
            )
            .order_by(Policy.renewal_date.asc().nullslast())
            .all()
        )

    def get_forward_projections(self, firm_id: int, months_ahead: int = 12) -> List[dict]:
        """Plan §🟢 #12 — quarterly projection of expected commission from
        ACTIVE policies whose renewal_date falls in the next `months_ahead`."""
        today = date.today()
        end = today + timedelta(days=months_ahead * 31)
        policies = (
            self.db.query(Policy)
            .filter(
                Policy.firm_id == firm_id,
                Policy.status == PolicyStatus.active,
                Policy.renewal_date.isnot(None),
                Policy.renewal_date >= today,
                Policy.renewal_date <= end,
            )
            .all()
        )
        buckets = _empty_quarter_buckets(today, end)
        for p in policies:
            if not p.renewal_date:
                continue
            key = _quarter_key(p.renewal_date)
            bucket = buckets.setdefault(
                key,
                {"period": key, "expected_commission": 0.0, "policy_count": 0},
            )
            bucket["expected_commission"] += _calc_policy_commission(p)
            bucket["policy_count"] += 1
        return [
            {**v, "expected_commission": round(v["expected_commission"], 2)}
            for v in sorted(buckets.values(), key=lambda b: b["period"])
        ]


def _quarter_key(d: date) -> str:
    return f"{d.year}-Q{(d.month - 1) // 3 + 1}"


def _empty_quarter_buckets(start: date, end: date) -> dict[str, dict]:
    """Build empty quarter buckets covering [start, end] so the chart x-axis
    has no gaps. Walks month-by-month and dedupes by quarter key."""
    buckets: dict[str, dict] = {}
    cursor = start
    while cursor <= end:
        key = _quarter_key(cursor)
        if key not in buckets:
            buckets[key] = {"period": key, "expected_commission": 0.0, "policy_count": 0}
        cursor = (cursor.replace(day=1) + timedelta(days=32)).replace(day=1)
    return buckets
