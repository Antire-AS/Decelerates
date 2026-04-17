"""Accounting integration endpoints — Tripletex and Fiken sync."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user, require_role
from api.dependencies import get_db
from api.services.accounting_service import AccountingService

router = APIRouter()


def _svc(db: Session = Depends(get_db)) -> AccountingService:
    return AccountingService(db)


@router.get("/accounting/status")
def get_accounting_status(
    svc: AccountingService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Return sync status for Tripletex and Fiken."""
    return svc.get_sync_status(user.firm_id)


@router.post("/accounting/sync/tripletex")
def sync_tripletex(
    svc: AccountingService = Depends(_svc),
    user: CurrentUser = Depends(require_role("admin")),
) -> dict:
    """Sync invoices to Tripletex. Requires admin role."""
    if not svc.is_tripletex_configured():
        raise HTTPException(
            status_code=503,
            detail="Tripletex er ikke konfigurert. Sett TRIPLETEX_API_KEY og TRIPLETEX_COMPANY_ID.",
        )
    return svc.sync_invoices_to_tripletex(user.firm_id)


@router.post("/accounting/sync/fiken")
def sync_fiken(
    svc: AccountingService = Depends(_svc),
    user: CurrentUser = Depends(require_role("admin")),
) -> dict:
    """Sync receipts to Fiken. Requires admin role."""
    if not svc.is_fiken_configured():
        raise HTTPException(
            status_code=503,
            detail="Fiken er ikke konfigurert. Sett FIKEN_ACCESS_TOKEN og FIKEN_COMPANY_SLUG.",
        )
    return svc.sync_receipts_to_fiken(user.firm_id)
