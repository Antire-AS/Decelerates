"""GDPR endpoints — right to erasure (Art. 17), data portability (Art. 20), retention purge, consent."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.dependencies import get_db
from api.domain.exceptions import NotFoundError
from api.schemas import ConsentOut
from api.services.consent_service import ConsentService
from api.services.audit import log_audit
from api.services.gdpr_service import GdprService

router = APIRouter()


def _gdpr_svc(db: Session = Depends(get_db)) -> GdprService:
    return GdprService(db)


def _consent_svc(db: Session = Depends(get_db)) -> ConsentService:
    return ConsentService(db)


class ConsentIn(BaseModel):
    lawful_basis: str  # consent | legitimate_interest | contract | legal_obligation
    purpose: str  # "insurance_advice" | "credit_check" | "marketing"


class ConsentWithdrawIn(BaseModel):
    reason: Optional[str] = None


def _serialize_consent(row) -> dict:
    return {
        "id": row.id,
        "orgnr": row.orgnr,
        "firm_id": row.firm_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "lawful_basis": row.lawful_basis.value,
        "purpose": row.purpose,
        "captured_by_email": row.captured_by_email,
        "withdrawn_at": row.withdrawn_at.isoformat() if row.withdrawn_at else None,
        "withdrawal_reason": row.withdrawal_reason,
    }


@router.delete("/gdpr/company/{orgnr}")
def erase_company(
    orgnr: str,
    db: Session = Depends(get_db),
    svc: GdprService = Depends(_gdpr_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Soft-delete a company (GDPR Art. 17). Clears PII; keeps financial history for compliance."""
    try:
        result = svc.erase_company(orgnr)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    log_audit(db, "gdpr.delete", orgnr=orgnr, detail={"action": "erase_company"})
    return result


@router.get("/gdpr/company/{orgnr}/export")
def export_company_data(
    orgnr: str,
    db: Session = Depends(get_db),
    svc: GdprService = Depends(_gdpr_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Export all data held for a company (GDPR Art. 20 — data portability)."""
    try:
        result = svc.export_company_data(orgnr)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    log_audit(db, "gdpr.export", orgnr=orgnr, detail={"action": "data_export"})
    return result


@router.post("/gdpr/purge")
def purge_old_deletions(
    svc: GdprService = Depends(_gdpr_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Hard-delete companies soft-deleted more than 90 days ago. Idempotent — safe for cron."""
    count = svc.purge_old_deletions()
    return {"purged": count}


# ── Consent management (GDPR Art. 6 / 7) ─────────────────────────────────────


@router.post("/gdpr/company/{orgnr}/consent", status_code=201)
def record_consent(
    orgnr: str,
    body: ConsentIn,
    db: Session = Depends(get_db),
    svc: ConsentService = Depends(_consent_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Record a GDPR lawful-basis consent for a client company."""
    row = svc.record_consent(
        orgnr, user.firm_id, user.email, body.lawful_basis, body.purpose
    )
    log_audit(
        db,
        "gdpr.consent.create",
        orgnr=orgnr,
        detail={"consent_id": row.id, "purpose": body.purpose},
    )
    return _serialize_consent(row)


@router.get("/gdpr/company/{orgnr}/consents", response_model=list[ConsentOut])
def get_active_consents(
    orgnr: str,
    svc: ConsentService = Depends(_consent_svc),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    """List active (non-withdrawn) consent records for a client."""
    rows = svc.get_active_consents(orgnr, user.firm_id)
    return [_serialize_consent(r) for r in rows]


@router.delete("/gdpr/company/{orgnr}/consent/{consent_id}", status_code=200)
def withdraw_consent(
    orgnr: str,
    consent_id: int,
    body: ConsentWithdrawIn,
    db: Session = Depends(get_db),
    svc: ConsentService = Depends(_consent_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Withdraw a previously recorded consent (GDPR Art. 7.3)."""
    try:
        row = svc.withdraw_consent(user.firm_id, consent_id, body.reason)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    log_audit(db, "gdpr.consent.delete", orgnr=orgnr, detail={"consent_id": consent_id})
    return _serialize_consent(row)
