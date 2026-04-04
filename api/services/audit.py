"""Audit logging helper — records key broker actions for compliance."""
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from api.db import AuditLog

_log = logging.getLogger(__name__)

# Financial services retention: 7 years
_AUDIT_RETENTION_DAYS = 365 * 7


def log_audit(
    db: Session,
    action: str,
    orgnr: Optional[str] = None,
    actor_email: Optional[str] = None,
    detail: Optional[dict] = None,
) -> None:
    """Append an immutable audit entry.

    Logs and rolls back on failure but does not re-raise — audit failures
    must never block the caller's business operation.
    """
    try:
        entry = AuditLog(
            orgnr=orgnr,
            actor_email=actor_email,
            action=action,
            detail=json.dumps(detail) if detail else None,
            created_at=datetime.now(timezone.utc),
        )
        db.add(entry)
        db.commit()
    except Exception as exc:
        _log.error("audit log write failed (action=%s orgnr=%s) — %s", action, orgnr, exc)
        db.rollback()


def purge_old_audit_logs(db: Session) -> int:
    """Hard-delete audit entries older than 7 years. Returns deleted count."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=_AUDIT_RETENTION_DAYS)
    deleted = (
        db.query(AuditLog)
        .filter(AuditLog.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted


def get_audit_summary(db: Session, firm_id: Optional[int] = None) -> dict:
    """Count audit entries by action for compliance reporting."""
    from sqlalchemy import func
    from api.db import Policy

    q = db.query(AuditLog.action, func.count(AuditLog.id).label("count"))
    if firm_id is not None:
        # Filter by orgnrs belonging to this firm
        orgnrs = [
            r.orgnr for r in db.query(Policy.orgnr).filter(Policy.firm_id == firm_id).distinct()
        ]
        if orgnrs:
            q = q.filter(AuditLog.orgnr.in_(orgnrs))

    rows = q.group_by(AuditLog.action).order_by(func.count(AuditLog.id).desc()).all()
    return {"by_action": {r.action: r.count for r in rows}}
