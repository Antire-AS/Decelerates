"""Coverage gap analysis endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.dependencies import get_db
from api.services.coverage_gap import analyze_coverage_gap

router = APIRouter()


@router.get("/org/{orgnr}/coverage-gap")
def get_coverage_gap(
    orgnr: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Return coverage gap analysis — active policies vs rule-engine recommendations."""
    return analyze_coverage_gap(orgnr, user.firm_id, db)
