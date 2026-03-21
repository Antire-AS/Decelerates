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


@router.get("/portfolio/{portfolio_id}/seed-norway/stream")
def stream_seed_norway(portfolio_id: int):
    """Stream live progress while seeding the portfolio with Norway's Top 100 companies.

    Looks each company up in BRREG by name as it goes, yielding NDJSON events.
    """
    def generate():
        from api.constants import TOP_100_NO_NAMES
        from api.services.external_apis import fetch_enhetsregisteret

        db = SessionLocal()
        try:
            existing = {
                pc.orgnr for pc in
                db.query(PortfolioCompany).filter(PortfolioCompany.portfolio_id == portfolio_id).all()
            }
            total = len(TOP_100_NO_NAMES)
            yield json.dumps({"type": "start", "total": total}) + "\n"

            added, skipped, not_found = 0, 0, 0
            for i, name in enumerate(TOP_100_NO_NAMES):
                yield json.dumps({"type": "searching", "name": name, "index": i + 1, "total": total}) + "\n"
                try:
                    results = fetch_enhetsregisteret(name, size=1)
                    if not results:
                        yield json.dumps({"type": "not_found", "name": name, "index": i + 1, "total": total}) + "\n"
                        not_found += 1
                        continue
                    orgnr = results[0]["orgnr"]
                    found_name = results[0]["navn"]
                    if orgnr in existing:
                        yield json.dumps({"type": "skipped", "name": found_name, "orgnr": orgnr, "index": i + 1, "total": total}) + "\n"
                        skipped += 1
                        continue
                    from datetime import datetime, timezone
                    db.add(PortfolioCompany(
                        portfolio_id=portfolio_id,
                        orgnr=orgnr,
                        added_at=datetime.now(timezone.utc).isoformat(),
                    ))
                    db.commit()
                    existing.add(orgnr)
                    yield json.dumps({"type": "added", "name": found_name, "orgnr": orgnr, "index": i + 1, "total": total}) + "\n"
                    added += 1
                except Exception as exc:
                    yield json.dumps({"type": "error", "name": name, "error": str(exc)[:100], "index": i + 1, "total": total}) + "\n"
                    not_found += 1

            yield json.dumps({"type": "complete", "added": added, "skipped": skipped, "not_found": not_found}) + "\n"
        finally:
            db.close()

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.post("/portfolio/{portfolio_id}/enrich-pdfs")
def enrich_pdfs(portfolio_id: int, svc: PortfolioService = Depends(_svc)) -> dict:
    """Trigger background PDF discovery + 5-year extraction for all companies in the portfolio.

    Returns immediately. Check /portfolio/{id}/risk for progress as data populates.
    """
    try:
        return svc.enrich_pdfs_background(portfolio_id)
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
