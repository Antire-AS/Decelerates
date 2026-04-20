"""Inbound mail webhook — parse insurer email replies into tender offers.

The broker's mail provider (SendGrid Inbound Parse, Mailgun Routes,
Postmark Inbound Webhook — all fit the same shape) POSTs new messages
to `/webhooks/tender-mail`. Each recipient in a tender has a unique
access_token; we tell insurers to reply to `tender-<token>@meglerai.no`
and use the local-part to route the attachment back to the right
tender + recipient without needing insurers to log into the portal.

Design notes:
- Pure functions here so the router stays thin and tests can run without
  HTTP/mail infra.
- `.pdf` attachments become TenderOffer rows (same path as portal upload).
- `.xlsx` / `.xls` attachments currently store as PDF-shaped TenderOffers
  with a flag — full Excel parsing (pandas/openpyxl) is a follow-up.
- Signature verification is up to the router; this module is payload-only.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from api.models.tender import TenderRecipient, TenderRecipientStatus
from api.services.tender_service import TenderService


# tender-<token>@<domain>  where <token> is URL-safe 32 chars (secrets.token_urlsafe(32))
_RECIPIENT_ADDRESS_RE = re.compile(r"^tender-([A-Za-z0-9_-]{20,64})@")

_PDF_MIME = "application/pdf"
_EXCEL_MIMES = (
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)


@dataclass
class InboundAttachment:
    filename: str
    content_type: str
    content_base64: str


@dataclass
class ParsedMail:
    to_address: str
    from_address: str
    subject: str
    attachments: list[InboundAttachment]


def parse_mail_payload(payload: dict[str, Any]) -> ParsedMail:
    """Normalise an incoming webhook payload to a `ParsedMail`.

    Accepts a conservative superset — looks up `to`/`from`/`subject`/
    `attachments` directly. Mail-provider-specific keys (e.g. SendGrid's
    `envelope`, Mailgun's `sender`) are mapped by the adapter layer before
    the payload reaches this function.
    """
    raw_atts = payload.get("attachments") or []
    atts: list[InboundAttachment] = []
    for a in raw_atts:
        if not isinstance(a, dict):
            continue
        fn = str(a.get("filename") or "").strip()
        ct = str(a.get("content_type") or "").strip()
        b64 = str(a.get("content_base64") or "").strip()
        if fn and b64:
            atts.append(
                InboundAttachment(filename=fn, content_type=ct, content_base64=b64)
            )
    return ParsedMail(
        to_address=str(payload.get("to") or "").strip(),
        from_address=str(payload.get("from") or "").strip(),
        subject=str(payload.get("subject") or "").strip(),
        attachments=atts,
    )


def extract_recipient_token(to_address: str) -> str | None:
    """Pull the tender recipient access_token from an address like
    `tender-<token>@broker.example`. Returns None if no match."""
    m = _RECIPIENT_ADDRESS_RE.match(to_address or "")
    return m.group(1) if m else None


def find_recipient(db: Session, token: str) -> TenderRecipient | None:
    svc = TenderService(db)
    return svc.get_recipient_by_token(token)


def _is_offer_attachment(att: InboundAttachment) -> bool:
    """True if the attachment looks like an insurance quote we can store."""
    name = att.filename.lower()
    if name.endswith(".pdf"):
        return True
    if name.endswith((".xlsx", ".xls")):
        return True
    ct = att.content_type.lower()
    return ct == _PDF_MIME or ct in _EXCEL_MIMES


def _decode_attachment(att: InboundAttachment) -> bytes | None:
    try:
        return base64.b64decode(att.content_base64)
    except (ValueError, TypeError):
        return None


def _store_attachments_as_offers(
    db: Session, recipient: TenderRecipient, attachments: list[InboundAttachment]
) -> tuple[list[int], list[str]]:
    """Loop over attachments, store valid ones as TenderOffer rows.
    Returns (stored_ids, skipped_reasons)."""
    svc = TenderService(db)
    stored: list[int] = []
    skipped: list[str] = []
    for att in attachments:
        if not _is_offer_attachment(att):
            skipped.append(f"{att.filename} (wrong type)")
            continue
        content = _decode_attachment(att)
        if content is None:
            skipped.append(f"{att.filename} (decode failed)")
            continue
        offer = svc.upload_offer(
            tender_id=recipient.tender_id,
            insurer_name=recipient.insurer_name,
            filename=att.filename,
            pdf_bytes=content,
            recipient_id=recipient.id,
        )
        stored.append(offer.id)
    return stored, skipped


def process_inbound_mail(db: Session, mail: ParsedMail) -> dict[str, Any]:
    """Route an inbound mail to a tender + recipient; store any offer attachments."""
    from datetime import datetime, timezone

    token = extract_recipient_token(mail.to_address)
    if not token:
        return {"matched": False, "reason": "no-token-in-address"}
    recipient = find_recipient(db, token)
    if recipient is None:
        return {"matched": False, "reason": "token-unknown"}

    stored, skipped = _store_attachments_as_offers(db, recipient, mail.attachments)
    if stored:
        recipient.status = TenderRecipientStatus.received
        recipient.response_at = datetime.now(timezone.utc)
        db.commit()

    return {
        "matched": True,
        "recipient_id": recipient.id,
        "tender_id": recipient.tender_id,
        "stored_offer_ids": stored,
        "skipped": skipped,
    }
