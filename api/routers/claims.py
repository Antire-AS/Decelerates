"""Claims tracking endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.dependencies import get_db
from api.domain.exceptions import NotFoundError
from api.schemas import ClaimIn, ClaimUpdate
from api.services.audit import log_audit
from api.services.claims_service import ClaimsService

router = APIRouter()


def _svc(db: Session = Depends(get_db)) -> ClaimsService:
    return ClaimsService(db)


def _serialize(c) -> dict:
    return {
        "id": c.id,
        "policy_id": c.policy_id,
        "orgnr": c.orgnr,
        "firm_id": c.firm_id,
        "claim_number": c.claim_number,
        "incident_date": c.incident_date.isoformat() if c.incident_date else None,
        "reported_date": c.reported_date.isoformat() if c.reported_date else None,
        "status": c.status.value,
        "description": c.description,
        "estimated_amount_nok": c.estimated_amount_nok,
        "settled_amount_nok": c.settled_amount_nok,
        "insurer_contact": c.insurer_contact,
        "notes": c.notes,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


@router.get("/org/{orgnr}/claims")
def list_claims(
    orgnr: str,
    svc: ClaimsService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    return [_serialize(c) for c in svc.list_by_orgnr(orgnr, user.firm_id)]


@router.post("/org/{orgnr}/claims", status_code=201)
def create_claim(
    orgnr: str,
    body: ClaimIn,
    svc: ClaimsService = Depends(_svc),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    try:
        c = svc.create(orgnr, user.firm_id, body)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    log_audit(
        db,
        "claim.create",
        orgnr=orgnr,
        actor_email=user.email,
        detail={"claim_number": c.claim_number},
    )
    return _serialize(c)


@router.put("/org/{orgnr}/claims/{claim_id}")
def update_claim(
    orgnr: str,
    claim_id: int,
    body: ClaimUpdate,
    svc: ClaimsService = Depends(_svc),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    try:
        c = svc.update(claim_id, user.firm_id, body)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    log_audit(
        db,
        "claim.update",
        orgnr=orgnr,
        actor_email=user.email,
        detail={"claim_id": claim_id},
    )
    return _serialize(c)


@router.delete("/org/{orgnr}/claims/{claim_id}", status_code=204)
def delete_claim(
    orgnr: str,
    claim_id: int,
    svc: ClaimsService = Depends(_svc),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    try:
        svc.delete(claim_id, user.firm_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    log_audit(
        db,
        "claim.delete",
        orgnr=orgnr,
        actor_email=user.email,
        detail={"claim_id": claim_id},
    )


@router.get("/policies/{policy_id}/claims")
def list_claims_by_policy(
    policy_id: int,
    svc: ClaimsService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    return [_serialize(c) for c in svc.list_by_policy(policy_id, user.firm_id)]
