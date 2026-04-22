"""Portfolio-level Altman Z'' risk aggregation endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.dependencies import get_db
from api.domain.exceptions import NotFoundError
from api.schemas import PortfolioRiskSummaryOut, PortfolioRiskRefreshOut
from api.services.portfolio_risk import (
    compute_and_store_snapshot,
    get_portfolio_risk_summary,
)

router = APIRouter()


@router.get(
    "/portfolio/{portfolio_id}/altman-risk", response_model=PortfolioRiskSummaryOut
)
def read_portfolio_risk(
    portfolio_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Return the latest snapshot summary. If no snapshot exists the response
    has empty zones / transitions — caller should POST /refresh first."""
    try:
        return get_portfolio_risk_summary(portfolio_id, user.firm_id, db)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/portfolio/{portfolio_id}/altman-risk/refresh",
    response_model=PortfolioRiskRefreshOut,
)
def refresh_portfolio_risk(
    portfolio_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Compute Altman Z'' for every company in the portfolio and store
    a new snapshot batch. Returns the new snapshot timestamp."""
    try:
        taken_at = compute_and_store_snapshot(portfolio_id, user.firm_id, db)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"portfolio_id": portfolio_id, "snapshot_at": taken_at.isoformat()}
