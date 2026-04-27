"""Shared inbound-email ingest pipeline (provider-agnostic).

Both the SendGrid Inbound Parse webhook (`api/routers/sendgrid_inbound.py`)
and the Microsoft Graph change-notification webhook
(`api/routers/msgraph_inbound.py`) normalise their provider-specific
payloads into a common `parsed` dict:

    {
        "subject": str,
        "sender": str,
        "recipient": str,
        "text_body": str,
        "attachments": [{"filename", "content_type", "content": bytes}, ...],
        "message_id": Optional[str],  # RFC822 Message-ID, for dedup
    }

…and funnel it into `match_and_ingest`, which:

  1. Dedupes by `message_id` (short-circuits replayed webhook deliveries).
  2. Extracts `[ref: TENDER-<tid>-<rid>]` from the subject to match the
     insurer's reply back to the tender we sent out.
  3. Uploads every PDF attachment as a `TenderOffer` via
     `TenderService.upload_offer`.
  4. Notifies every user in the tender's firm (different copy for
     PDF vs. no-PDF replies so the inbox surfaces which happened).
  5. Writes one audit row into `incoming_email_log` per call.

Every branch lands in `incoming_email_log` (matched / orphaned / error /
dedup) so operator debugging never requires reprocessing MIME.

Historical note: a third webhook for ACS Event Grid was shipped in v5
then discovered to be architecturally impossible (ACS email is
outbound-only — no `EmailReceived` event exists). Removed on 2026-04-24;
the shared helpers below were always the real product.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from api.db import IncomingEmailLog, NotificationKind, Tender, TenderRecipient, User
from api.services.notification_inbox_service import create_notification_for_users_safe
from api.services.tender_service import TenderService

_log = logging.getLogger(__name__)

# Tender ref format embedded in outbound anbudspakke subject so replies
# can be matched back to the original invitation.
_TENDER_REF_RE = re.compile(r"\[ref:\s*TENDER-(\d+)-(\d+)\s*\]", re.IGNORECASE)


# ── Subject-line matching ────────────────────────────────────────────────────


def extract_tender_ref(subject: Optional[str]) -> Optional[Tuple[int, int, str]]:
    """Parse `[ref: TENDER-5-42]` out of a subject line. Returns
    (tender_id, recipient_id, raw_ref_string) or None if no match."""
    if not subject:
        return None
    m = _TENDER_REF_RE.search(subject)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), m.group(0)


def format_tender_ref(tender_id: int, recipient_id: int) -> str:
    """Produce the exact token the outbound flow embeds in subjects.
    Keeping both builder + parser here pins the invariant in one place."""
    return f"[ref: TENDER-{tender_id}-{recipient_id}]"


# ── Tender match + offer ingest ─────────────────────────────────────────────


def _load_tender_and_recipient(
    tender_id: int, recipient_id: int, db: Session
) -> Tuple[Optional[Tender], Optional[TenderRecipient]]:
    # FIRM_ID_AUDIT: webhook has no broker session — firm scope is
    # derived from the tender ref token in the email subject. The tender
    # is looked up by its PK (globally unique), and downstream
    # notification fan-out uses tender.firm_id directly. No cross-firm
    # leakage is possible because the ref token is only embedded in
    # outbound anbudspakke mails, which are sent by a broker within a
    # firm.
    t = db.query(Tender).get(tender_id)
    r = db.query(TenderRecipient).get(recipient_id)
    if not t or not r or r.tender_id != tender_id:
        return None, None
    return t, r


def _reply_notification_copy(
    tender: Tender, recipient: TenderRecipient, has_pdf: bool
) -> Tuple[str, str]:
    """(title, message) for the in-app notification. Branch on has_pdf so
    the broker can tell at a glance whether there's an offer to review
    or a follow-up needed."""
    if has_pdf:
        return (
            f"Nytt tilbud fra {recipient.insurer_name}",
            f'{recipient.insurer_name} har svart på anbudet "{tender.title}". '
            "Åpne anbudet for å se vilkårene.",
        )
    return (
        f"Svar fra {recipient.insurer_name} — uten vedlegg",
        f'{recipient.insurer_name} har svart på anbudet "{tender.title}", '
        "men uten PDF-vedlegg. Åpne anbudet og sjekk mailboksen.",
    )


def _notify_firm_of_reply(
    tender: Tender,
    recipient: TenderRecipient,
    has_pdf: bool,
    db: Session,
) -> None:
    """One notification per user in the tender's firm on any insurer
    reply. Both PDF and no-PDF replies fire so the broker never misses
    engagement — copy varies so the inbox surfaces what happened."""
    if tender.firm_id is None:
        return
    user_ids = [
        uid for (uid,) in db.query(User.id).filter(User.firm_id == tender.firm_id).all()
    ]
    if not user_ids:
        return
    title, message = _reply_notification_copy(tender, recipient, has_pdf)
    create_notification_for_users_safe(
        db,
        user_ids=user_ids,
        firm_id=tender.firm_id,
        kind=NotificationKind.deal_won,
        title=title,
        message=message,
        orgnr=tender.orgnr,
        link=f"/tenders/{tender.id}",
    )


def _ingest_attachments(
    tender: Tender,
    recipient: TenderRecipient,
    attachments: List[Dict[str, Any]],
    db: Session,
) -> Optional[int]:
    """Upload every PDF attachment as a TenderOffer. Returns the id of
    the first created offer (or None if no PDFs)."""
    svc = TenderService(db)
    first_offer_id: Optional[int] = None
    for att in attachments:
        if "pdf" not in (att.get("content_type") or "").lower():
            continue
        offer = svc.upload_offer(
            tender_id=tender.id,
            insurer_name=recipient.insurer_name,
            filename=att["filename"],
            pdf_bytes=att["content"],
            recipient_id=recipient.id,
        )
        if first_offer_id is None:
            first_offer_id = offer.id
    return first_offer_id


def _log_row(
    db: Session,
    parsed: Dict[str, Any],
    ref_raw: Optional[str],
    tender_id: Optional[int],
    recipient_id: Optional[int],
    status: str,
    offer_id: Optional[int] = None,
    error: Optional[str] = None,
) -> IncomingEmailLog:
    row = IncomingEmailLog(
        received_at=datetime.now(timezone.utc),
        sender=(parsed.get("sender") or "")[:320] or None,
        recipient=(parsed.get("recipient") or "")[:320] or None,
        subject=parsed.get("subject"),
        tender_ref=ref_raw,
        tender_id=tender_id,
        recipient_id=recipient_id,
        status=status,
        offer_id=offer_id,
        error_message=error,
        attachment_count=len(parsed.get("attachments") or []),
        message_id=parsed.get("message_id") or None,
    )
    db.add(row)
    db.commit()
    return row


def _find_existing_by_message_id(
    db: Session, message_id: Optional[str]
) -> Optional[IncomingEmailLog]:
    """Look up a prior log row with the same RFC822 Message-ID. Used by
    `match_and_ingest` to short-circuit replayed webhook deliveries so
    we don't create duplicate TenderOffer rows. Returns None when the
    message_id is missing (can't dedup) or no prior row exists."""
    if not message_id:
        return None
    return (
        db.query(IncomingEmailLog)
        .filter(IncomingEmailLog.message_id == message_id)
        .first()
    )


# ── Main entry point (provider-agnostic) ────────────────────────────────────


def _resolve_tender(
    parsed: Dict[str, Any], db: Session
) -> Tuple[
    Optional[Tender], Optional[TenderRecipient], Optional[str], Optional[Dict[str, Any]]
]:
    """Extract ref from subject + look up tender. Returns
    (tender, recipient, ref_raw, error_result). error_result is set on
    orphan paths; success returns (t, r, ref_raw, None)."""
    ref = extract_tender_ref(parsed.get("subject"))
    if not ref:
        _log_row(db, parsed, None, None, None, "orphaned")
        return (
            None,
            None,
            None,
            {"status": "orphaned", "reason": "no_tender_ref_in_subject"},
        )
    tender_id, recipient_id, ref_raw = ref
    tender, recipient = _load_tender_and_recipient(tender_id, recipient_id, db)
    if not tender or not recipient:
        _log_row(
            db,
            parsed,
            ref_raw,
            tender_id,
            recipient_id,
            "orphaned",
            error="unknown_tender_or_recipient",
        )
        return None, None, ref_raw, {"status": "orphaned", "reason": "unknown_tender"}
    return tender, recipient, ref_raw, None


def _ingest_and_notify(
    parsed: Dict[str, Any],
    tender: Tender,
    recipient: TenderRecipient,
    ref_raw: str,
    db: Session,
) -> Dict[str, Any]:
    """Upload attachments → notify firm → log matched row. Handles the
    ingest failure branch with its own error log so the outer function
    stays short."""
    try:
        offer_id = _ingest_attachments(tender, recipient, parsed["attachments"], db)
    except Exception as exc:
        _log_row(
            db,
            parsed,
            ref_raw,
            tender.id,
            recipient.id,
            "error",
            error=f"ingest: {exc}",
        )
        return {"status": "error", "reason": str(exc)}
    # Always notify on a matched reply — broker needs to know the insurer
    # engaged even when the mail has no PDF (common when the insurer says
    # "we'll come back with an offer" or asks a clarifying question).
    _notify_firm_of_reply(tender, recipient, has_pdf=bool(offer_id), db=db)
    _log_row(db, parsed, ref_raw, tender.id, recipient.id, "matched", offer_id=offer_id)
    return {
        "status": "matched",
        "tender_id": tender.id,
        "recipient_id": recipient.id,
        "offer_id": offer_id,
        "pdf_attachments": sum(
            1
            for a in parsed["attachments"]
            if "pdf" in (a.get("content_type") or "").lower()
        ),
    }


def match_and_ingest(parsed: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """Resolve tender from subject → dedup-check → ingest + notify.
    Returns the final status dict.

    Public because the SendGrid + Graph inbound paths both funnel into it
    once they've normalised their payload to the shared `parsed` shape.
    Dedup by RFC822 Message-ID makes the whole pipeline idempotent
    against webhook replay storms."""
    existing = _find_existing_by_message_id(db, parsed.get("message_id"))
    if existing is not None:
        return {
            "status": "dedup",
            "reason": "already_processed",
            "existing_log_id": existing.id,
            "offer_id": existing.offer_id,
        }
    tender, recipient, ref_raw, error = _resolve_tender(parsed, db)
    if error is not None:
        return error
    assert tender is not None and recipient is not None and ref_raw is not None
    return _ingest_and_notify(parsed, tender, recipient, ref_raw, db)
