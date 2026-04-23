"""Admin surface for the inbound-email audit log.

Read-only paged view of `incoming_email_log` with a status filter. Lets
an admin answer "did this reply actually reach us?" without hitting
Postgres directly.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.auth import CurrentUser, require_role
from api.db import IncomingEmailLog
from api.dependencies import get_db
from api.schemas import IncomingEmailLogEntryOut, IncomingEmailLogPageOut

router = APIRouter()


_ALLOWED_STATUSES = {"matched", "orphaned", "error", "dedup"}


def _serialize(r: IncomingEmailLog) -> IncomingEmailLogEntryOut:
    return IncomingEmailLogEntryOut(
        id=r.id,  # type: ignore[arg-type]
        received_at=r.received_at,  # type: ignore[arg-type]
        sender=r.sender,  # type: ignore[arg-type]
        recipient=r.recipient,  # type: ignore[arg-type]
        subject=r.subject,  # type: ignore[arg-type]
        tender_ref=r.tender_ref,  # type: ignore[arg-type]
        tender_id=r.tender_id,  # type: ignore[arg-type]
        recipient_id=r.recipient_id,  # type: ignore[arg-type]
        status=r.status,  # type: ignore[arg-type]
        error_message=r.error_message,  # type: ignore[arg-type]
        attachment_count=r.attachment_count,  # type: ignore[arg-type]
        offer_id=r.offer_id,  # type: ignore[arg-type]
        message_id=r.message_id,  # type: ignore[arg-type]
    )


@router.get(
    "/admin/email-log",
    response_model=IncomingEmailLogPageOut,
)
def list_email_log(
    status: Optional[str] = Query(
        default=None,
        description="Filter by status: matched / orphaned / error / dedup",
    ),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_role("admin")),
) -> IncomingEmailLogPageOut:
    """Page through the inbound-email audit log, newest first."""
    q = db.query(IncomingEmailLog).order_by(IncomingEmailLog.received_at.desc())
    if status and status in _ALLOWED_STATUSES:
        q = q.filter(IncomingEmailLog.status == status)
    total = q.count()
    rows = q.offset(offset).limit(limit).all()
    items = [_serialize(r) for r in rows]
    return IncomingEmailLogPageOut(
        items=items,
        total=total,
        offset=offset,
        limit=limit,
        has_more=(offset + len(items)) < total,
    )
