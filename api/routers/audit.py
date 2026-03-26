"""Audit log endpoints — read-only access to the broker action trail."""
import csv
import io
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.db import AuditLog
from api.dependencies import get_db

router = APIRouter()


@router.get("/audit/export")
def export_audit_csv(
    orgnr: Optional[str] = Query(default=None),
    limit: int = Query(default=500, le=2000),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    """Export audit log as UTF-8 CSV (BOM for Excel compatibility)."""
    q = db.query(AuditLog).order_by(AuditLog.created_at.desc())
    if orgnr:
        q = q.filter(AuditLog.orgnr == orgnr)
    rows = q.limit(limit).all()

    buf = io.StringIO()
    fields = ["id", "created_at", "orgnr", "action", "actor_email", "detail"]
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    for r in rows:
        writer.writerow({
            "id": r.id,
            "created_at": r.created_at.isoformat(),
            "orgnr": r.orgnr or "",
            "action": r.action,
            "actor_email": r.actor_email or "",
            "detail": r.detail or "",
        })

    filename = f"audit_{date.today()}.csv"
    content = buf.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
