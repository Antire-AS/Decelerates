"""Webhook receivers — plan §🟢 #11 (Signicat) + future integrations.

Webhook endpoints are PUBLIC (no auth dependency) — they're called by
external services that don't carry our Azure AD tokens. Security comes from
HMAC signature verification on the raw request body. NEVER trust an unsigned
webhook payload.
"""

import json
import logging
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from api.dependencies import get_db
from api.schemas import SignicatWebhookAck
from api.services.audit import log_audit
from api.services.docuseal_service import DocuSealService
from api.services.mail_webhook import parse_mail_payload, process_inbound_mail
from api.services.recommendation_service import RecommendationService
from api.services.signicat_service import SignicatService
from api.services.tender_service import TenderService

router = APIRouter()
_log = logging.getLogger(__name__)


@router.post("/webhooks/signicat", response_model=SignicatWebhookAck)
async def signicat_webhook(
    request: Request,
    x_signicat_signature: str = Header(default=""),
    db: Session = Depends(get_db),
) -> dict:
    """Receive a signing-status callback from Signicat. Verifies HMAC
    signature, then updates the matching Recommendation row."""
    raw_body = await request.body()
    signicat = SignicatService()
    if not signicat.is_configured():
        # Return 503 (not 401) so Signicat retries until we're configured
        # rather than blackballing the endpoint as a bad receiver.
        raise HTTPException(status_code=503, detail="Signicat not configured")
    if not signicat.verify_webhook(raw_body, x_signicat_signature):
        _log.warning("Signicat webhook signature mismatch — refusing payload")
        raise HTTPException(status_code=401, detail="Invalid signature")
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    parsed = signicat.parse_webhook(payload)
    if parsed["status"] in ("signed", "completed"):
        RecommendationService(db).mark_signed_by_session(
            parsed["session_id"],
            signed_pdf_blob_url=parsed.get("signed_pdf_url"),
        )
    log_audit(
        db,
        "webhook.signicat",
        detail={"session_id": parsed.get("session_id"), "status": parsed.get("status")},
    )
    return {"received": True}


def _verify_mail_webhook_secret(provided: str) -> None:
    """Raise 503/401 if the shared-secret header doesn't match env config."""
    expected = os.getenv("MAIL_WEBHOOK_SECRET", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Mail webhook not configured")
    if not provided or provided != expected:
        _log.warning("tender-mail webhook: secret mismatch")
        raise HTTPException(status_code=401, detail="Invalid secret")


@router.post("/webhooks/tender-mail")
async def tender_mail_webhook(
    request: Request,
    x_mail_webhook_secret: str = Header(default=""),
    db: Session = Depends(get_db),
) -> dict:
    """Receive an inbound email from the broker's mail provider and route
    attachments to the matching tender + recipient.

    Recipients are identified by the `To:` local-part: insurers reply to
    `tender-<access_token>@broker.example`. Auth is a shared secret in
    `X-Mail-Webhook-Secret` (env `MAIL_WEBHOOK_SECRET`).
    """
    _verify_mail_webhook_secret(x_mail_webhook_secret)
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    mail = parse_mail_payload(payload)
    result = process_inbound_mail(db, mail)
    log_audit(
        db,
        "webhook.tender_mail",
        detail={
            "to": mail.to_address,
            "from": mail.from_address,
            "matched": result.get("matched"),
            "stored": len(result.get("stored_offer_ids", [])),
        },
    )
    return {"received": True, **result}


def _verify_docuseal_and_parse(
    docuseal: DocuSealService, raw_body: bytes, signature: str
) -> dict:
    """Check config + HMAC + decode body. Raises the right HTTP status so
    the route stays thin."""
    if not docuseal.is_configured():
        # 503 (not 401) so DocuSeal retries until we're configured rather than
        # blackballing the endpoint.
        raise HTTPException(status_code=503, detail="DocuSeal not configured")
    if not docuseal.verify_webhook(raw_body, signature):
        _log.warning("DocuSeal webhook signature mismatch — refusing payload")
        raise HTTPException(status_code=401, detail="Invalid signature")
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    return docuseal.parse_webhook(payload)


@router.post("/webhooks/docuseal")
async def docuseal_webhook(
    request: Request,
    x_docuseal_signature: str = Header(default=""),
    db: Session = Depends(get_db),
) -> dict:
    """Receive a DocuSeal form-status callback. Verifies HMAC signature, then
    flips the matching tender row to `analysed` once the client has signed.

    The webhook carries DocuSeal's submission_id. The broker's
    `/tenders/{id}/contract/send-for-signature` call persisted that same ID
    onto `tenders.contract_session_id`, so the lookup is O(1) via the partial
    unique index on that column.

    Unknown session IDs are ACK'd with `matched: false` — DocuSeal retries
    failed deliveries, and we don't want to turn a replay (or a submission
    created outside this flow) into a 4xx loop.
    """
    raw_body = await request.body()
    parsed = _verify_docuseal_and_parse(
        DocuSealService(), raw_body, x_docuseal_signature
    )
    matched = False
    if parsed["status"] in ("signed", "completed"):
        tender = TenderService(db).mark_contract_signed_by_session(parsed["session_id"])
        matched = tender is not None
    log_audit(
        db,
        "webhook.docuseal",
        detail={
            "session_id": parsed.get("session_id"),
            "status": parsed.get("status"),
            "matched": matched,
        },
    )
    return {"received": True, "matched": matched}
