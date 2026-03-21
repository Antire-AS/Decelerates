"""Portfolio endpoints — named company lists with risk analysis and cross-company chat."""
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session

from api.dependencies import get_db
from api.domain.exceptions import NotFoundError
from api.limiter import limiter
from api.schemas import PortfolioCreate, PortfolioAddCompany, ChatRequest
from api.services.portfolio import PortfolioService

router = APIRouter()


def _svc(db: Session = Depends(get_db)) -> PortfolioService:
    return PortfolioService(db)


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.post("/portfolio")
def create_portfolio(body: PortfolioCreate, svc: PortfolioService = Depends(_svc)) -> dict:
    p = svc.create(body.name, body.description or "")
    return {"id": p.id, "name": p.name, "description": p.description, "created_at": p.created_at}


@router.get("/portfolio")
def list_portfolios(svc: PortfolioService = Depends(_svc)) -> list:
    return [
        {"id": p.id, "name": p.name, "description": p.description, "created_at": p.created_at}
        for p in svc.list_portfolios()
    ]


@router.delete("/portfolio/{portfolio_id}")
def delete_portfolio(portfolio_id: int, svc: PortfolioService = Depends(_svc)) -> dict:
    try:
        svc.delete(portfolio_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"deleted": portfolio_id}


@router.post("/portfolio/{portfolio_id}/companies")
def add_company(portfolio_id: int, body: PortfolioAddCompany, svc: PortfolioService = Depends(_svc)) -> dict:
    try:
        svc.add_company(portfolio_id, body.orgnr)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"portfolio_id": portfolio_id, "orgnr": body.orgnr}


@router.delete("/portfolio/{portfolio_id}/companies/{orgnr}")
def remove_company(portfolio_id: int, orgnr: str, svc: PortfolioService = Depends(_svc)) -> dict:
    svc.remove_company(portfolio_id, orgnr)
    return {"portfolio_id": portfolio_id, "orgnr": orgnr}


# ── Analysis ──────────────────────────────────────────────────────────────────

@router.get("/portfolio/{portfolio_id}/risk")
def get_portfolio_risk(portfolio_id: int, svc: PortfolioService = Depends(_svc)) -> list:
    """Return risk summary for every company in the portfolio, sorted by risk score."""
    try:
        return svc.get_risk_summary(portfolio_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/portfolio/{portfolio_id}/ingest")
def ingest_portfolio(portfolio_id: int, svc: PortfolioService = Depends(_svc)) -> dict:
    """Batch-fetch BRREG + financial data for all companies not yet in the database."""
    try:
        return svc.ingest_companies(portfolio_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/portfolio/{portfolio_id}/chat")
@limiter.limit("10/minute")
def portfolio_chat(
    request: Request,
    portfolio_id: int,
    body: ChatRequest,
    svc: PortfolioService = Depends(_svc),
) -> dict:
    """Answer a question grounded in the financial data of all companies in the portfolio."""
    try:
        return svc.chat(portfolio_id, body.question)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
