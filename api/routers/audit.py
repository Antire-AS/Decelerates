"""Audit log endpoints — read-only access to the broker action trail."""

import csv
import io
from datetime import date, datetime, time
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Query as OrmQuery, Session

from api.auth import CurrentUser, get_current_user
from api.db import AuditLog
from api.dependencies import get_db
from api.schemas import AuditLogPageOut

router = APIRouter()


def _apply_filters(
    q: "OrmQuery[AuditLog]",
    *,
    orgnr: Optional[str],
    action: Optional[str],
    actor_email: Optional[str],
    from_date: Optional[date],
    to_date: Optional[date],
) -> "OrmQuery[AuditLog]":
    """Compose the WHERE clauses for /audit and /audit/export so the two
    endpoints stay in lock-step. Filters are AND'd; absent filters are no-ops."""
    if orgnr:
        q = q.filter(AuditLog.orgnr == orgnr)
    if action:
        q = q.filter(AuditLog.action == action)
    if actor_email:
        q = q.filter(AuditLog.actor_email == actor_email)
    if from_date:
        q = q.filter(AuditLog.created_at >= datetime.combine(from_date, time.min))
    if to_date:
        q = q.filter(AuditLog.created_at <= datetime.combine(to_date, time.max))
    return q


def _serialize(r: AuditLog) -> dict:
    return {
        "id": r.id,
        "orgnr": r.orgnr,
        "action": r.action,
        "actor_email": r.actor_email,
        "detail": r.detail,
        "created_at": r.created_at,
    }


@router.get("/audit/export")
def export_audit_csv(
    orgnr: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    actor_email: Optional[str] = Query(default=None),
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
    limit: int = Query(default=500, le=2000),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    """Export audit log as UTF-8 CSV (BOM for Excel compatibility)."""
    q = _apply_filters(
        db.query(AuditLog).order_by(AuditLog.created_at.desc()),
        orgnr=orgnr,
        action=action,
        actor_email=actor_email,
        from_date=from_date,
        to_date=to_date,
    )
    rows = q.limit(limit).all()

    buf = io.StringIO()
    fields = ["id", "created_at", "orgnr", "action", "actor_email", "detail"]
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    for r in rows:
        writer.writerow(
            {
                "id": r.id,
                "created_at": r.created_at.isoformat(),
                "orgnr": r.orgnr or "",
                "action": r.action,
                "actor_email": r.actor_email or "",
                "detail": r.detail or "",
            }
        )

    filename = f"audit_{date.today()}.csv"
    content = buf.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/audit/{orgnr}", response_model=AuditLogPageOut)
def get_audit_log(
    orgnr: str,
    action: Optional[str] = Query(default=None),
    actor_email: Optional[str] = Query(default=None),
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Paginated audit entries for a specific company (newest first)."""
    return _query_audit_page(
        db,
        orgnr=orgnr,
        action=action,
        actor_email=actor_email,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )


@router.get("/audit", response_model=AuditLogPageOut)
def get_audit_log_global(
    orgnr: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    actor_email: Optional[str] = Query(default=None),
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Paginated audit entries across all companies (newest first)."""
    return _query_audit_page(
        db,
        orgnr=orgnr,
        action=action,
        actor_email=actor_email,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )


def _query_audit_page(
    db: Session,
    *,
    orgnr: Optional[str],
    action: Optional[str],
    actor_email: Optional[str],
    from_date: Optional[date],
    to_date: Optional[date],
    limit: int,
    offset: int,
) -> dict:
    base = _apply_filters(
        db.query(AuditLog),
        orgnr=orgnr,
        action=action,
        actor_email=actor_email,
        from_date=from_date,
        to_date=to_date,
    )
    total = base.count()
    rows = base.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "items": [_serialize(r) for r in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": (offset + len(rows)) < total,
    }
