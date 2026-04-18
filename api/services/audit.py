"""Audit logging helper — records key broker actions for compliance."""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from api.db import AuditLog

logger = logging.getLogger(__name__)

_AUDIT_RETENTION_DAYS = 365 * 7


class AuditService:
    """Immutable audit trail for compliance and debugging."""

    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        action: str,
        orgnr: Optional[str] = None,
        actor_email: Optional[str] = None,
        detail: Optional[dict] = None,
    ) -> None:
        try:
            entry = AuditLog(
                orgnr=orgnr,
                actor_email=actor_email,
                action=action,
                detail=json.dumps(detail) if detail else None,
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(entry)
            self.db.commit()
        except Exception as exc:
            logger.error(
                "audit log write failed (action=%s orgnr=%s) — %s", action, orgnr, exc
            )
            self.db.rollback()

    def purge_old(self) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=_AUDIT_RETENTION_DAYS)
        deleted = (
            self.db.query(AuditLog)
            .filter(AuditLog.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        self.db.commit()
        return deleted

    def get_summary(self, firm_id: Optional[int] = None) -> dict:
        from sqlalchemy import func
        from api.db import Policy

        q = self.db.query(AuditLog.action, func.count(AuditLog.id).label("count"))
        if firm_id is not None:
            orgnrs = [
                r.orgnr
                for r in self.db.query(Policy.orgnr)
                .filter(Policy.firm_id == firm_id)
                .distinct()
            ]
            if orgnrs:
                q = q.filter(AuditLog.orgnr.in_(orgnrs))

        rows = (
            q.group_by(AuditLog.action).order_by(func.count(AuditLog.id).desc()).all()
        )
        return {"by_action": {r.action: r.count for r in rows}}


# ── Backward-compat module-level functions ──────────────────────────────────


def log_audit(db: Session, action: str, orgnr=None, actor_email=None, detail=None):
    AuditService(db).log(action, orgnr=orgnr, actor_email=actor_email, detail=detail)


def purge_old_audit_logs(db: Session) -> int:
    return AuditService(db).purge_old()


def get_audit_summary(db: Session, firm_id=None) -> dict:
    return AuditService(db).get_summary(firm_id)
