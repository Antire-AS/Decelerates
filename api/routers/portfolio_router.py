"""Portfolio endpoints — named company lists with risk analysis and cross-company chat."""
import json

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api.db import PortfolioCompany, Company
from api.db import SessionLocal
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


@router.get("/portfolio/{portfolio_id}/ingest/stream")
def stream_ingest_portfolio(portfolio_id: int):
    """Stream live progress of portfolio ingest as newline-delimited JSON.

    Each line is a JSON object with fields: type, orgnr, navn, risk_score, index, total.
    Types: start | searching | done | skipped | error | complete
    """
    def generate():
        db = SessionLocal()
        try:
            rows = db.query(PortfolioCompany).filter(PortfolioCompany.portfolio_id == portfolio_id).all()
            total = len(rows)
            yield json.dumps({"type": "start", "total": total}) + "\n"

            from api.services.company import fetch_org_profile
            for i, pc in enumerate(rows):
                existing = db.query(Company).filter(Company.orgnr == pc.orgnr).first()
                navn = (existing.navn if existing else None) or pc.orgnr

                if existing and existing.navn and existing.risk_score is not None:
                    yield json.dumps({
                        "type": "skipped", "orgnr": pc.orgnr, "navn": navn,
                        "risk_score": existing.risk_score, "index": i + 1, "total": total,
                    }) + "\n"
                    continue

                yield json.dumps({
                    "type": "searching", "orgnr": pc.orgnr, "navn": navn,
                    "index": i + 1, "total": total,
                }) + "\n"

                try:
                    fetch_org_profile(pc.orgnr, db)
                    company = db.query(Company).filter(Company.orgnr == pc.orgnr).first()
                    yield json.dumps({
                        "type": "done", "orgnr": pc.orgnr,
                        "navn": (company.navn if company else navn),
                        "risk_score": (company.risk_score if company else None),
                        "index": i + 1, "total": total,
                    }) + "\n"
                except Exception as exc:
                    yield json.dumps({
                        "type": "error", "orgnr": pc.orgnr, "navn": navn,
                        "error": str(exc)[:120], "index": i + 1, "total": total,
                    }) + "\n"

            yield json.dumps({"type": "complete", "total": total}) + "\n"
        finally:
            db.close()

    return StreamingResponse(generate(), media_type="application/x-ndjson")


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
