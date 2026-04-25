"""One-click demo-tender seeder for /admin.

Puts a fresh Tender for Bergmann Industri AS in the DB with 3 insurer
recipients routed to Gmail + alias addresses, so the broker can go
straight from "Start ny demo-tender" in /admin → send invites → reply
from Gmail with one of the offer PDFs in docs/demo-data/.

Scope: demo/hardening only. Idempotency: upserts the Bergmann Company
row so repeated clicks don't clutter the companies table, but always
creates a fresh Tender so you can demo multiple times back-to-back.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.auth import CurrentUser, require_role
from api.db import BrokerFirm
from api.dependencies import get_db
from api.services.demo_tender_service import upsert_demo_bergmann
from api.services.tender_service import TenderService

router = APIRouter()


class SeededTenderOut(BaseModel):
    tender_id: int
    url: str
    orgnr: str
    recipients: list[dict]


def _resolve_firm_id(db: Session, user: CurrentUser) -> int:
    """Pick the firm to create the tender under. Uses the admin's own
    firm_id when available; falls back to the single-tenant pattern
    used by cron endpoints when there's exactly one BrokerFirm."""
    if user.firm_id:
        return int(user.firm_id)
    count = db.query(BrokerFirm).count()
    if count != 1:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot resolve firm — {count} firms found, no user firm_id.",
        )
    firm = db.query(BrokerFirm).first()
    if firm is None:
        raise HTTPException(status_code=503, detail="No BrokerFirm configured.")
    return int(firm.id)  # type: ignore[arg-type]


def _demo_recipients(broker_email: str) -> list[dict]:
    """Generate 3 insurer recipient dicts routing to Gmail `+alias`
    addresses the broker controls. Default broker_email is the one
    configured in SENDGRID_FORWARD_TO — falls back to a placeholder if
    unset (dev only)."""
    base = broker_email.split("@")
    if len(base) == 2:
        local, domain = base
    else:
        local, domain = "demo", "example.com"
    return [
        {
            "insurer_name": "Gjensidige Forsikring",
            "insurer_email": f"{local}+gjensidige@{domain}",
        },
        {"insurer_name": "If Skadeforsikring", "insurer_email": f"{local}+if@{domain}"},
        {"insurer_name": "Tryg Forsikring", "insurer_email": f"{local}+tryg@{domain}"},
    ]


@router.post("/admin/seed-demo-tender", response_model=SeededTenderOut)
def seed_demo_tender(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("admin")),
) -> SeededTenderOut:
    """Seed Bergmann Industri AS + a fresh Tender with 3 pre-populated
    insurer recipients. Returns the tender URL so the frontend can
    redirect the broker straight to it."""
    company = upsert_demo_bergmann(db)
    firm_id = _resolve_firm_id(db, user)
    broker_email = os.getenv("SENDGRID_FORWARD_TO", "demo@example.com")
    recipients = _demo_recipients(broker_email)
    svc = TenderService(db)
    tender = svc.create(
        orgnr=company.orgnr,  # type: ignore[arg-type]
        firm_id=firm_id,
        title=f"Demo: Forsikringsanbud {company.navn}",  # type: ignore[arg-type]
        product_types=["bygning", "ansvar", "avbrudd"],
        notes="Auto-generert demo-tender. Send invitasjoner og svar fra Gmail med en av tilbud_*.pdf-filene.",
        created_by_email=user.email,  # type: ignore[arg-type]
        recipients=recipients,
    )
    return SeededTenderOut(
        tender_id=int(tender.id),  # type: ignore[arg-type]
        url=f"/tenders/{tender.id}",
        orgnr=str(company.orgnr),  # type: ignore[arg-type]
        recipients=recipients,
    )
