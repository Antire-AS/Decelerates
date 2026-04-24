"""SendGrid Inbound Parse webhook.

Complements the Graph-based inbound flow. SendGrid posts each inbound
mail as `multipart/form-data` — we normalise to the shared `parsed`
dict shape and delegate to `match_and_ingest`. An optional forward
step mirrors the mail into a personal inbox so a human can still see
every reply in their normal email client.

Security:
- Webhook URL carries a secret token (`?token=<value>`) that we compare
  against `SENDGRID_INBOUND_TOKEN`. SendGrid has no native HMAC on
  Inbound Parse, and a sufficiently-random URL is the standard stop-gap.
  Unset token disables the check (dev only).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from api.dependencies import get_db
from api.services.inbound_email_service import match_and_ingest
from api.services.sendgrid_inbound_service import (
    SendGridConfig,
    forward_copy_via_sendgrid,
    is_configured,
    normalise_inbound_form,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_config() -> SendGridConfig:
    return SendGridConfig(
        api_key=os.getenv("SENDGRID_API_KEY", ""),
        inbound_token=os.getenv("SENDGRID_INBOUND_TOKEN", ""),
        forward_to=os.getenv("SENDGRID_FORWARD_TO", ""),
        forward_from=os.getenv("SENDGRID_FORWARD_FROM", ""),
    )


def _token_ok(config: SendGridConfig, token: Optional[str]) -> bool:
    """Shared-secret gate. Disabled when SENDGRID_INBOUND_TOKEN unset so
    first-run + local dev work without fiddling."""
    if not config.inbound_token:
        return True
    return token == config.inbound_token


@router.post("/webhooks/sendgrid/inbound", include_in_schema=False)
async def sendgrid_inbound(
    request: Request,
    token: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    config = _get_config()
    if not is_configured(config):
        logger.warning("sendgrid_inbound: SENDGRID_API_KEY missing — rejecting batch")
        return {"status": "skipped", "reason": "sendgrid_not_configured"}
    if not _token_ok(config, token):
        logger.warning("sendgrid_inbound: token mismatch — dropping batch")
        return {"status": "skipped", "reason": "token_mismatch"}
    try:
        form = await request.form()
        form_dict = dict(form)
    except Exception as exc:
        logger.exception("sendgrid_inbound: form parse failed")
        return {"status": "error", "reason": f"parse: {exc}"}
    parsed = normalise_inbound_form(form_dict)
    result = match_and_ingest(parsed, db)
    # Forward AFTER ingest so a failure in Mail Send doesn't block the
    # ingest ack. match_and_ingest already handles logging.
    forward_copy_via_sendgrid(config, parsed)
    return result
