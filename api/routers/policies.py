"""Policy register and renewal pipeline endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.container import resolve
from api.dependencies import get_db
from api.domain.exceptions import NotFoundError, ValidationError
from api.ports.driven.notification_port import NotificationPort
from api.schemas import PolicyIn, PolicyUpdate, RenewalAdvanceIn
from api.services.audit import log_audit
from api.services.policy_service import PolicyService

router = APIRouter()


def _svc(db: Session = Depends(get_db)) -> PolicyService:
    return PolicyService(db)


def _get_notification() -> NotificationPort:
    return resolve(NotificationPort)  # type: ignore[return-value]


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
        "renewal_stage":       p.renewal_stage.value if p.renewal_stage else "not_started",
        "notes":               p.notes,
        "document_url":        p.document_url,
        "created_at":          p.created_at.isoformat() if p.created_at else None,
        "updated_at":          p.updated_at.isoformat() if p.updated_at else None,
    }


@router.get("/org/{orgnr}/policies")
def list_policies(
    orgnr: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    svc: PolicyService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    return [_serialize(p) for p in svc.list_by_orgnr(orgnr, user.firm_id, skip=skip, limit=limit)]


@router.post("/org/{orgnr}/policies", status_code=201)
def create_policy(
    orgnr: str,
    body: PolicyIn,
    svc: PolicyService = Depends(_svc),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    try:
        p = svc.create(orgnr, user.firm_id, body)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    log_audit(db, "policy.create", orgnr=orgnr, actor_email=user.email,
              detail={"policy_number": p.policy_number, "insurer": p.insurer})
    return _serialize(p)


@router.put("/org/{orgnr}/policies/{policy_id}")
def update_policy(
    orgnr: str,
    policy_id: int,
    body: PolicyUpdate,
    svc: PolicyService = Depends(_svc),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    try:
        p = svc.update(policy_id, user.firm_id, body)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    log_audit(db, "policy.update", orgnr=orgnr, actor_email=user.email,
              detail={"policy_id": policy_id})
    return _serialize(p)


@router.delete("/org/{orgnr}/policies/{policy_id}", status_code=204)
def delete_policy(
    orgnr: str,
    policy_id: int,
    svc: PolicyService = Depends(_svc),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    try:
        svc.delete(policy_id, user.firm_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    log_audit(db, "policy.delete", orgnr=orgnr, actor_email=user.email,
              detail={"policy_id": policy_id})


@router.get("/policies")
def list_all_policies(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    svc: PolicyService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    """All policies for the current firm."""
    return [_serialize(p) for p in svc.list_by_firm(user.firm_id, skip=skip, limit=limit)]


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


@router.post("/policies/{policy_id}/renewal/advance")
def advance_renewal_stage(
    policy_id: int,
    body: RenewalAdvanceIn,
    svc: PolicyService = Depends(_svc),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    notification: NotificationPort = Depends(_get_notification),
) -> dict:
    """Advance the renewal workflow stage for a policy and optionally notify by email."""
    try:
        policy = svc.advance_renewal_stage(policy_id, user.firm_id, body.stage)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    log_audit(db, "policy.renewal.stage_change", orgnr=policy.orgnr,
              actor_email=user.email, detail={"policy_id": policy_id, "stage": body.stage})

    if body.notify_email:
        notification.send_renewal_stage_change(
            to=body.notify_email,
            policy_number=policy.policy_number or f"#{policy.id}",
            insurer=policy.insurer,
            product_type=policy.product_type,
            stage=body.stage,
        )

    return _serialize(policy)
