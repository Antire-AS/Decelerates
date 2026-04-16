"""Dashboard summary endpoint."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.db import Policy, PolicyStatus, Claim, ClaimStatus, Activity
from api.dependencies import get_db

router = APIRouter()


@router.get("/dashboard")
def get_dashboard(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Broker dashboard summary — renewals, claims, activities, premium book."""
    today = date.today()
    firm_id = user.firm_id

    renewals_30 = db.query(Policy).filter(
        Policy.firm_id == firm_id, Policy.status == PolicyStatus.active,
        Policy.renewal_date >= today, Policy.renewal_date <= today + timedelta(days=30),
    ).all()
    renewals_90 = db.query(Policy).filter(
        Policy.firm_id == firm_id, Policy.status == PolicyStatus.active,
        Policy.renewal_date >= today, Policy.renewal_date <= today + timedelta(days=90),
    ).all()

    active_policies = db.query(Policy).filter(
        Policy.firm_id == firm_id, Policy.status == PolicyStatus.active,
    ).all()
    total_premium = sum(p.annual_premium_nok or 0 for p in active_policies)

    open_claims = db.query(Claim).filter(
        Claim.firm_id == firm_id, Claim.status == ClaimStatus.open,
    ).count()

    due_today = db.query(Activity).filter(
        Activity.firm_id == firm_id, Activity.completed == False,  # noqa: E712
        Activity.due_date <= today,
    ).count()

    recent = db.query(Activity).filter(
        Activity.firm_id == firm_id,
    ).order_by(Activity.created_at.desc()).limit(5).all()

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
                "subject": a.subject, "type": a.activity_type.value,
                "orgnr": a.orgnr, "created_by": a.created_by_email,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "completed": a.completed,
            }
            for a in recent
        ],
    }
