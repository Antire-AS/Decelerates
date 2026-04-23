"""ACS Event Grid webhook for inbound email."""

import logging
from typing import Any, List

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from api.dependencies import get_db
from api.services.inbound_email_service import (
    _is_email_received_event,
    build_validation_response,
    process_email_received_event,
)

router = APIRouter()

logger = logging.getLogger(__name__)


def _normalize_events(payload: Any) -> List[dict]:
    """Event Grid sends a JSON array even for single events. Some SDK
    versions wrap in {"events": [...]} — handle both shapes so the
    handler below always iterates a flat list."""
    if isinstance(payload, dict) and "events" in payload:
        return payload["events"]
    if isinstance(payload, list):
        return payload
    return [payload]


def _process_events(events: List[dict], db: Session) -> List[dict]:
    """Run the inbound pipeline per event. Unhandled exceptions are
    caught so a single bad email never blocks the queue — they're
    logged here and recorded as `status=error` in the per-event row."""
    results: List[dict] = []
    for event in events:
        if not _is_email_received_event(event):
            results.append({"status": "skipped", "type": event.get("eventType")})
            continue
        try:
            results.append(process_email_received_event(event, db))
        except Exception as exc:
            logger.exception("Unhandled error processing EmailReceived event")
            results.append({"status": "error", "reason": str(exc)})
    return results


@router.post("/webhooks/acs/email-received")
async def acs_email_received(
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Event Grid push endpoint for ACS EmailReceived events.

    Two response modes:

    1. First call after an Event Grid subscription is created: the
       payload is a SubscriptionValidationEvent with data.validationCode.
       We MUST echo it back as {"validationResponse": code} or the
       subscription never activates.
    2. Subsequent calls: array of events. We always return 200 even if
       individual events failed and log errors to incoming_email_log —
       non-2xx makes Event Grid retry for ~24h, which is not what we
       want for malformed MIME.
    """
    events = _normalize_events(await request.json())
    validation = build_validation_response(events)
    if validation is not None:
        return JSONResponse(content=validation, status_code=200)
    results = _process_events(events, db)
    return {"processed": len(results), "results": results}
