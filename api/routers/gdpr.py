"""GDPR endpoints — right to erasure (Art. 17), data portability (Art. 20), retention purge."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.dependencies import get_db
from api.domain.exceptions import NotFoundError
from api.services.gdpr_service import GdprService

router = APIRouter()


def _gdpr_svc(db: Session = Depends(get_db)) -> GdprService:
    return GdprService(db)


@router.delete("/gdpr/company/{orgnr}")
def erase_company(
    orgnr: str,
    svc: GdprService = Depends(_gdpr_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Soft-delete a company (GDPR Art. 17). Clears PII; keeps financial history for compliance."""
    try:
        return svc.erase_company(orgnr)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/gdpr/company/{orgnr}/export")
def export_company_data(
    orgnr: str,
    svc: GdprService = Depends(_gdpr_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Export all data held for a company (GDPR Art. 20 — data portability)."""
    try:
        return svc.export_company_data(orgnr)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/gdpr/purge")
def purge_old_deletions(
    svc: GdprService = Depends(_gdpr_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Hard-delete companies soft-deleted more than 90 days ago. Idempotent — safe for cron."""
    count = svc.purge_old_deletions()
    return {"purged": count}
