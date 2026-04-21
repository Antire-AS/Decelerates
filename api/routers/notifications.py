"""In-app notifications router — bell-icon backend.

Plan §🟢 #17. Each endpoint declares response_model so the api-types-fresh
gate locks the contract. We need a real numeric user_id (not just firm_id)
because notifications are per-user; that means resolving the User row from
the Azure OID on every call.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.db import User
from api.dependencies import get_db
from api.domain.exceptions import NotFoundError
from api.schemas import (
    NotificationListOut,
    NotificationMarkReadOut,
    NotificationOut,
)
from api.services.audit import log_audit
from api.services.notification_inbox_service import NotificationInboxService

router = APIRouter()


def _resolve_user_id(db: Session, user: CurrentUser) -> int:
    """Look up the numeric users.id from the Azure OID. Returns 404 if the
    user record hasn't been auto-provisioned yet (shouldn't happen in
    practice — first login provisions via UserService.get_or_create).

    # FIRM_ID_AUDIT: azure_oid is globally unique per user; firm_id would be
    # redundant scoping and block legitimate first-login lookups.
    """
    row = db.query(User).filter(User.azure_oid == user.oid).first()
    if not row:
        raise HTTPException(status_code=404, detail="User record not found")
    return row.id  # type: ignore[return-value]


def _serialize(n) -> dict:
    return {
        "id": n.id,
        "user_id": n.user_id,
        "firm_id": n.firm_id,
        "orgnr": n.orgnr,
        "kind": n.kind.value,
        "title": n.title,
        "message": n.message,
        "link": n.link,
        "read": n.read,
        "created_at": n.created_at,
    }


@router.get("/notifications", response_model=NotificationListOut)
def list_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    user_id = _resolve_user_id(db, user)
    svc = NotificationInboxService(db)
    items = svc.list_for_user(user_id, unread_only=unread_only, limit=limit)
    unread_count = svc.unread_count(user_id)
    return {
        "items": [_serialize(n) for n in items],
        "unread_count": unread_count,
    }


@router.patch("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    user_id = _resolve_user_id(db, user)
    try:
        notif = NotificationInboxService(db).mark_read(notification_id, user_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    log_audit(db, "notification.read", detail={"notification_id": notification_id})
    return _serialize(notif)


@router.post("/notifications/read-all", response_model=NotificationMarkReadOut)
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    user_id = _resolve_user_id(db, user)
    updated = NotificationInboxService(db).mark_all_read(user_id)
    log_audit(db, "notification.read_all", detail={"updated": updated})
    return {"updated": updated}
