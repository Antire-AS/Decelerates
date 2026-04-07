"""Activity timeline / CRM log endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.dependencies import get_db
from api.domain.exceptions import NotFoundError
from api.schemas import (
    ActivityBulkComplete,
    ActivityBulkCompleteOut,
    ActivityIn,
    ActivityUpdate,
)
from api.services.activity_service import ActivityService
from api.services.audit import log_audit

router = APIRouter()


def _svc(db: Session = Depends(get_db)) -> ActivityService:
    return ActivityService(db)


def _serialize(a) -> dict:
    return {
        "id":                  a.id,
        "orgnr":               a.orgnr,
        "firm_id":             a.firm_id,
        "policy_id":           a.policy_id,
        "claim_id":            a.claim_id,
        "created_by_email":    a.created_by_email,
        "assigned_to_user_id": a.assigned_to_user_id,
        "activity_type":       a.activity_type.value,
        "subject":             a.subject,
        "body":                a.body,
        "due_date":            a.due_date.isoformat() if a.due_date else None,
        "completed":           a.completed,
        "created_at":          a.created_at.isoformat() if a.created_at else None,
    }


@router.get("/org/{orgnr}/activities")
def list_activities(
    orgnr: str,
    limit: int = Query(default=50, ge=1, le=200),
    svc: ActivityService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    return [_serialize(a) for a in svc.list_by_orgnr(orgnr, user.firm_id, limit)]


@router.post("/org/{orgnr}/activities", status_code=201)
def create_activity(
    orgnr: str,
    body: ActivityIn,
    svc: ActivityService = Depends(_svc),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    try:
        a = svc.create(orgnr, user.firm_id, user.email, body)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    log_audit(db, "activity.create", orgnr=orgnr, actor_email=user.email,
              detail={"activity_type": body.activity_type, "subject": body.subject})
    return _serialize(a)


@router.put("/org/{orgnr}/activities/{activity_id}")
def update_activity(
    orgnr: str,
    activity_id: int,
    body: ActivityUpdate,
    svc: ActivityService = Depends(_svc),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    try:
        a = svc.update(activity_id, user.firm_id, body)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    log_audit(db, "activity.update", orgnr=orgnr, actor_email=user.email,
              detail={"activity_id": activity_id})
    return _serialize(a)


@router.delete("/org/{orgnr}/activities/{activity_id}", status_code=204)
def delete_activity(
    orgnr: str,
    activity_id: int,
    svc: ActivityService = Depends(_svc),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    try:
        svc.delete(activity_id, user.firm_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    log_audit(db, "activity.delete", orgnr=orgnr, actor_email=user.email,
              detail={"activity_id": activity_id})


@router.post("/activities/bulk-complete", response_model=ActivityBulkCompleteOut)
def bulk_complete_activities(
    body: ActivityBulkComplete,
    svc: ActivityService = Depends(_svc),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Plan §🟢 #18 — bulk-mark activities completed."""
    updated = svc.bulk_complete(body.activity_ids, user.firm_id)
    log_audit(db, "activity.bulk_complete", actor_email=user.email,
              detail={"count": updated})
    return {"updated": updated}
