"""Policy register and renewal pipeline endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.dependencies import get_db
from api.domain.exceptions import NotFoundError
from api.schemas import PolicyIn, PolicyUpdate
from api.services.policy_service import PolicyService

router = APIRouter()


def _svc(db: Session = Depends(get_db)) -> PolicyService:
    return PolicyService(db)


def _serialize(p) -> dict:
    return {
        "id":                  p.id,
        "orgnr":               p.orgnr,
        "firm_id":             p.firm_id,
        "contact_person_id":   p.contact_person_id,
        "policy_number":       p.policy_number,
        "insurer":             p.insurer,
        "product_type":        p.product_type,
        "coverage_amount_nok": p.coverage_amount_nok,
        "annual_premium_nok":  p.annual_premium_nok,
        "start_date":          p.start_date.isoformat() if p.start_date else None,
        "renewal_date":        p.renewal_date.isoformat() if p.renewal_date else None,
        "status":              p.status.value,
        "notes":               p.notes,
        "created_at":          p.created_at.isoformat() if p.created_at else None,
        "updated_at":          p.updated_at.isoformat() if p.updated_at else None,
    }


@router.get("/org/{orgnr}/policies")
def list_policies(
    orgnr: str,
    svc: PolicyService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    return [_serialize(p) for p in svc.list_by_orgnr(orgnr, user.firm_id)]


@router.post("/org/{orgnr}/policies", status_code=201)
def create_policy(
    orgnr: str,
    body: PolicyIn,
    svc: PolicyService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    try:
        return _serialize(svc.create(orgnr, user.firm_id, body))
    except NotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/org/{orgnr}/policies/{policy_id}")
def update_policy(
    orgnr: str,
    policy_id: int,
    body: PolicyUpdate,
    svc: PolicyService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    try:
        return _serialize(svc.update(policy_id, user.firm_id, body))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/org/{orgnr}/policies/{policy_id}", status_code=204)
def delete_policy(
    orgnr: str,
    policy_id: int,
    svc: PolicyService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    try:
        svc.delete(policy_id, user.firm_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/policies")
def list_all_policies(
    svc: PolicyService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    """All policies for the current firm."""
    return [_serialize(p) for p in svc.list_by_firm(user.firm_id)]


@router.get("/renewals")
def get_renewals(
    days: int = Query(default=90, ge=1, le=365),
    svc: PolicyService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    """Active policies renewing within the next N days (default 90)."""
    from datetime import date
    policies = svc.get_renewals(user.firm_id, days)
    today = date.today()
    result = []
    for p in policies:
        serialized = _serialize(p)
        if p.renewal_date:
            serialized["days_to_renewal"] = (p.renewal_date - today).days
        result.append(serialized)
    return result


@router.get("/renewals/upcoming")
def get_upcoming_renewals(
    days: int = Query(default=30, ge=1, le=365),
    svc: PolicyService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    """Alias for /renewals with a 30-day default window."""
    from datetime import date
    policies = svc.get_renewals(user.firm_id, days)
    today = date.today()
    result = []
    for p in policies:
        serialized = _serialize(p)
        if p.renewal_date:
            serialized["days_to_renewal"] = (p.renewal_date - today).days
        result.append(serialized)
    return result
