"""Dashboard summary endpoint."""

from calendar import monthrange
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.db import Policy, PolicyStatus, Claim, ClaimStatus, Activity
from api.dependencies import get_db
from api.schemas.dashboard import PremiumTrendOut, PremiumTrendPoint
from api.schemas.recommendations import (
    DashboardRecommendationsOut,
    RecommendationOut,
)
from api.services.recommendations_engine import compute_recommendations

router = APIRouter()


@router.get("/dashboard")
def get_dashboard(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Broker dashboard summary — renewals, claims, activities, premium book."""
    today = date.today()
    firm_id = user.firm_id

    renewals_30 = (
        db.query(Policy)
        .filter(
            Policy.firm_id == firm_id,
            Policy.status == PolicyStatus.active,
            Policy.renewal_date >= today,
            Policy.renewal_date <= today + timedelta(days=30),
        )
        .all()
    )
    renewals_90 = (
        db.query(Policy)
        .filter(
            Policy.firm_id == firm_id,
            Policy.status == PolicyStatus.active,
            Policy.renewal_date >= today,
            Policy.renewal_date <= today + timedelta(days=90),
        )
        .all()
    )

    active_policies = (
        db.query(Policy)
        .filter(
            Policy.firm_id == firm_id,
            Policy.status == PolicyStatus.active,
        )
        .all()
    )
    total_premium = sum(p.annual_premium_nok or 0 for p in active_policies)

    open_claims = (
        db.query(Claim)
        .filter(
            Claim.firm_id == firm_id,
            Claim.status == ClaimStatus.open,
        )
        .count()
    )

    due_today = (
        db.query(Activity)
        .filter(
            Activity.firm_id == firm_id,
            Activity.completed == False,  # noqa: E712
            Activity.due_date <= today,
        )
        .count()
    )

    recent = (
        db.query(Activity)
        .filter(
            Activity.firm_id == firm_id,
        )
        .order_by(Activity.created_at.desc())
        .limit(5)
        .all()
    )

    return {
        "renewals_30d": len(renewals_30),
        "renewals_90d": len(renewals_90),
        "premium_at_risk_30d": sum(p.annual_premium_nok or 0 for p in renewals_30),
        "open_claims": open_claims,
        "activities_due": due_today,
        "total_active_policies": len(active_policies),
        "total_premium_book": total_premium,
        "recent_activities": [
            {
                "subject": a.subject,
                "type": a.activity_type.value,
                "orgnr": a.orgnr,
                "created_by": a.created_by_email,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "completed": a.completed,
            }
            for a in recent
        ],
    }


def _month_end(today: date, months_ago: int) -> date:
    """Return the last calendar day of (today minus `months_ago` months)."""
    year = today.year
    month = today.month - months_ago
    while month <= 0:
        month += 12
        year -= 1
    last_day = monthrange(year, month)[1]
    return date(year, month, last_day)


@router.get("/dashboard/premium-trend", response_model=PremiumTrendOut)
def get_premium_trend(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> PremiumTrendOut:
    """12 monthly snapshots of active-policy premium-book, oldest first.

    A policy is "active at month-end" when:
      - start_date <= month_end_date, AND
      - renewal_date IS NULL OR renewal_date > month_end_date.

    Status filter is intentionally omitted so historical snapshots are
    stable even if the policy is later cancelled.
    """
    today = date.today()
    firm_id = user.firm_id

    points: list[PremiumTrendPoint] = []
    for i in range(11, -1, -1):
        m_end = _month_end(today, i)
        total = (
            db.query(func.coalesce(func.sum(Policy.annual_premium_nok), 0.0))
            .filter(
                Policy.firm_id == firm_id,
                Policy.start_date <= m_end,
                or_(Policy.renewal_date.is_(None), Policy.renewal_date > m_end),
            )
            .scalar()
        ) or 0.0
        points.append(
            PremiumTrendPoint(month=m_end.strftime("%Y-%m"), premium_book=float(total))
        )

    oldest = points[0].premium_book
    newest = points[-1].premium_book
    yoy = None if oldest <= 0 else round(((newest - oldest) / oldest) * 100, 1)

    return PremiumTrendOut(months=points, yoy_delta_pct=yoy)


def _firm_company_rows(db: Session, firm_id: int):
    """Return Company rows for organizations the firm is brokering for.

    Companies aren't directly firm-scoped — they're shared. We use the
    Policy table to derive which orgnrs this firm cares about.
    """
    from api.db import Company

    orgnr_rows = (
        db.query(Policy.orgnr)
        .filter(Policy.firm_id == firm_id)
        .distinct()
        .all()
    )
    orgnrs = [r[0] for r in orgnr_rows if r[0]]
    if not orgnrs:
        return []
    return db.query(Company).filter(Company.orgnr.in_(orgnrs)).all()


def _build_companies_payload(rows) -> list[dict]:
    out = []
    for c in rows:
        pep = c.pep_raw if isinstance(c.pep_raw, dict) else {}
        out.append(
            {
                "orgnr": c.orgnr,
                "navn": c.navn,
                "pep_hit_count": int(pep.get("hit_count") or 0),
            }
        )
    return out


def _build_claims_index(db: Session, firm_id: int) -> dict:
    """Most-recent incident_date per orgnr (falls back to created_at)."""
    rows = (
        db.query(
            Claim.orgnr,
            func.max(func.coalesce(Claim.incident_date, Claim.created_at)).label("last"),
        )
        .filter(Claim.firm_id == firm_id)
        .group_by(Claim.orgnr)
        .all()
    )
    return {orgnr: last for orgnr, last in rows if orgnr and last}


@router.get(
    "/dashboard/recommendations",
    response_model=DashboardRecommendationsOut,
)
def get_dashboard_recommendations(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> DashboardRecommendationsOut:
    """Top-5 actionable recommendations for the broker (mockup 10.55.56).

    Signals wired:
      - companies: Company rows for orgnrs the firm has policies on
      - claims_index: most-recent claim date per orgnr (incident_date fallback created_at)
      - last_narrative_at: empty for now — narrative-at column not in schema yet,
        so the stale_narrative rule fires whenever there's a fresh claim
      - peer_overage_orgnrs: empty for now — compute_peer_benchmark is too
        expensive to run per-company on every dashboard load; deferred to a
        nightly cache table
    """
    rows = _firm_company_rows(db, user.firm_id)
    companies = _build_companies_payload(rows)
    claims_index = _build_claims_index(db, user.firm_id)
    items = compute_recommendations(
        companies=companies,
        claims_index=claims_index,
        last_narrative_at={},
        peer_overage_orgnrs=set(),
    )
    return DashboardRecommendationsOut(items=[RecommendationOut(**i) for i in items])
