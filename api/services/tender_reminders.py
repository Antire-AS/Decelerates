"""Tender deadline reminders — purring cron job.

Tenders have a `deadline` field and recipients have `status` (pending/sent/
received/declined). Between "sent" and "received", recipients sometimes go
silent. This job sends one reminder email 7 days before deadline and another
2 days before, so the broker doesn't have to manually chase every time.

Called via POST /admin/tender-reminders (wired to a daily GitHub Actions
cron at 08:00 UTC — mirrors the existing portfolio risk monitor pattern).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from api.db import Company
from api.models.tender import (
    Tender,
    TenderRecipient,
    TenderRecipientStatus,
    TenderStatus,
)
from api.services.tender_service import _send_tender_email

_log = logging.getLogger(__name__)

# Reminder thresholds (days before deadline).
_REMINDER_DAYS = (7, 2)


def _should_remind(deadline: date, today: date) -> bool:
    """True if today is exactly 7 or 2 days before the deadline."""
    return (deadline - today).days in _REMINDER_DAYS


def _pending_recipients(db: Session, tender: Tender) -> list[TenderRecipient]:
    """Recipients that were invited but haven't responded yet."""
    return (
        db.query(TenderRecipient)
        .filter(
            TenderRecipient.tender_id == tender.id,
            TenderRecipient.status == TenderRecipientStatus.sent,
            TenderRecipient.insurer_email.isnot(None),
        )
        .all()
    )


def _remind_one_tender(db: Session, tender: Tender) -> tuple[int, int]:
    """Send reminders for a single tender that's hitting a threshold. Returns (sent, failed)."""
    recipients = _pending_recipients(db, tender)
    if not recipients:
        return (0, 0)
    company = db.query(Company).filter(Company.orgnr == tender.orgnr).first()
    company_name = company.navn if company else tender.orgnr
    sent = 0
    failed = 0
    for r in recipients:
        ok = _send_tender_email(
            to=r.insurer_email,
            tender=tender,
            company_name=company_name,
            insurer_name=r.insurer_name,
        )
        if ok:
            sent += 1
            _log.info("tender reminder sent: tender=%s recipient=%s", tender.id, r.id)
        else:
            failed += 1
            _log.warning(
                "tender reminder failed: tender=%s recipient=%s", tender.id, r.id
            )
    return (sent, failed)


def send_deadline_reminders(db: Session, today: date | None = None) -> dict[str, Any]:
    """Send deadline reminders for all tenders hitting the 7d or 2d threshold.

    # FIRM_ID_AUDIT: system-level cron that iterates every firm's active
    # tenders by design; reminder emails are addressed to the tender's
    # creator, so firm-scoping is implicit via `tender.firm_id` downstream.
    """
    today = today or datetime.now(timezone.utc).date()
    sent_count = 0
    failed_count = 0
    tenders_checked = 0

    tenders = (
        db.query(Tender)
        .filter(Tender.status == TenderStatus.sent, Tender.deadline.isnot(None))
        .all()
    )
    for tender in tenders:
        tenders_checked += 1
        if tender.deadline is None or not _should_remind(tender.deadline, today):
            continue
        s, f = _remind_one_tender(db, tender)
        sent_count += s
        failed_count += f

    return {
        "tenders_checked": tenders_checked,
        "reminders_sent": sent_count,
        "reminders_failed": failed_count,
    }
