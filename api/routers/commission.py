"""Commission and revenue tracking endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.dependencies import get_db
from api.schemas import CommissionClientOut, CommissionSummaryOut, PolicyMissingOut
from api.services.commission_service import CommissionService

router = APIRouter()


def _svc(db: Session = Depends(get_db)) -> CommissionService:
    return CommissionService(db)


@router.get("/commission/summary", response_model=CommissionSummaryOut)
def get_commission_summary(
    svc: CommissionService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Revenue and commission totals for the firm."""
    return svc.get_commission_summary(user.firm_id)


@router.get("/commission/by-client/{orgnr}", response_model=CommissionClientOut)
def get_commission_by_client(
    orgnr: str,
    svc: CommissionService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Commission breakdown for a single client company."""
    return svc.get_commission_by_client(user.firm_id, orgnr)


@router.get("/commission/missing", response_model=list[PolicyMissingOut])
def list_policies_missing_commission(
    svc: CommissionService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    """Active policies with no commission rate or amount recorded."""
    policies = svc.list_policies_missing_commission(user.firm_id)
    return [
        {
            "id":             p.id,
            "orgnr":          p.orgnr,
            "policy_number":  p.policy_number,
            "product_type":   p.product_type,
            "insurer":        p.insurer,
            "annual_premium_nok": p.annual_premium_nok,
            "renewal_date":   p.renewal_date.isoformat() if p.renewal_date else None,
        }
        for p in policies
    ]
