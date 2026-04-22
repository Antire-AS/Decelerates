"""Altman Z''-Score historical trend endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.dependencies import get_db
from api.schemas import AltmanHistoryOut
from api.services.risk_history import get_altman_z_history

router = APIRouter()


@router.get("/org/{orgnr}/altman-history", response_model=AltmanHistoryOut)
def get_altman_history(orgnr: str, db: Session = Depends(get_db)) -> dict:
    """Return one Altman Z'' data point per year of available financial history.

    Years with partial extractions (e.g. missing current-assets split) are
    omitted — the frontend should render a sparse line, not interpolate.
    """
    return {"orgnr": orgnr, "points": get_altman_z_history(db, orgnr)}
