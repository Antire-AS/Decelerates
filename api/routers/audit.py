"""Audit log endpoints — read-only access to the broker action trail."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.db import AuditLog
from api.dependencies import get_db

router = APIRouter()


@router.get("/audit/{orgnr}")
def get_audit_log(
    orgnr: str,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    """Return recent audit entries for a specific company (newest first)."""
    rows = (
        db.query(AuditLog)
        .filter(AuditLog.orgnr == orgnr)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "action": r.action,
            "actor_email": r.actor_email,
            "detail": r.detail,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/audit")
def get_audit_log_global(
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    """Return recent audit entries across all companies (newest first)."""
    rows = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "orgnr": r.orgnr,
            "action": r.action,
            "actor_email": r.actor_email,
            "detail": r.detail,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
