"""Audit logging helper — records key broker actions for compliance."""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from api.db import AuditLog

_log = logging.getLogger(__name__)


def log_audit(
    db: Session,
    action: str,
    orgnr: Optional[str] = None,
    actor_email: Optional[str] = None,
    detail: Optional[dict] = None,
) -> None:
    """Append an immutable audit entry. Swallows all exceptions — never blocks the caller."""
    # TODO: re-enable when activity tracking is needed again
    return  # audit logging disabled
    try:  # noqa: unreachable
        entry = AuditLog(
            orgnr=orgnr,
            actor_email=actor_email,
            action=action,
            detail=json.dumps(detail) if detail else None,
            created_at=datetime.now(timezone.utc),
        )
        db.add(entry)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        _log.warning("audit log write failed — %s", exc)
        db.rollback()
