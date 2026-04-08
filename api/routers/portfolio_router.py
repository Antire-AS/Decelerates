"""Portfolio endpoints — named company lists with risk analysis and cross-company chat."""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.db import PortfolioCompany, Company, Portfolio, SessionLocal
from api.dependencies import get_db
from api.domain.exceptions import NotFoundError
from api.limiter import limiter
from api.schemas import (
    PortfolioCreate,
    PortfolioAddCompany,
    PortfolioBulkAdd,
    PortfolioBulkAddOut,
    ChatRequest,
)
from api.services.portfolio import PortfolioService, collect_alerts

router = APIRouter()


def _svc(db: Session = Depends(get_db)) -> PortfolioService:
    return PortfolioService(db)


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.post("/portfolio")
def create_portfolio(
    body: PortfolioCreate,
    svc: PortfolioService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    p = svc.create(body.name, user.firm_id, body.description or "")
    return {"id": p.id, "name": p.name, "description": p.description, "created_at": p.created_at}


@router.get("/portfolio")
def list_portfolios(
    svc: PortfolioService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    return [
        {"id": p.id, "name": p.name, "description": p.description, "created_at": p.created_at}
        for p in svc.list_portfolios(user.firm_id)
    ]


@router.get("/portfolio/{portfolio_id}")
def get_portfolio(
    portfolio_id: int,
    svc: PortfolioService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    try:
        p = svc.get(portfolio_id, user.firm_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"id": p.id, "name": p.name, "description": p.description, "created_at": p.created_at}


@router.delete("/portfolio/{portfolio_id}")
def delete_portfolio(
    portfolio_id: int,
    svc: PortfolioService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    try:
        svc.delete(portfolio_id, user.firm_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"deleted": portfolio_id}


@router.post("/portfolio/{portfolio_id}/companies")
def add_company(
    portfolio_id: int,
    body: PortfolioAddCompany,
    svc: PortfolioService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    try:
        svc.add_company(portfolio_id, body.orgnr)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"portfolio_id": portfolio_id, "orgnr": body.orgnr}


@router.post("/portfolio/{portfolio_id}/companies/bulk", response_model=PortfolioBulkAddOut)
def add_companies_bulk(
    portfolio_id: int,
    body: PortfolioBulkAdd,
    svc: PortfolioService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Plan §🟢 #18 — bulk-add companies to a portfolio. Skips orgnrs that
    are already members; returns added/skipped counts. Resolves the portfolio
    once up front so we get a clean 404 instead of N failures."""
    try:
        svc.get(portfolio_id, user.firm_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    added = skipped = 0
    for orgnr in body.orgnrs:
        try:
            svc.add_company(portfolio_id, orgnr)
            added += 1
        except Exception:
            # Already-member, missing company, etc. — count and continue.
            skipped += 1
    return {"added": added, "skipped": skipped}


@router.delete("/portfolio/{portfolio_id}/companies/{orgnr}")
def remove_company(
    portfolio_id: int,
    orgnr: str,
    svc: PortfolioService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    svc.remove_company(portfolio_id, orgnr)
    return {"portfolio_id": portfolio_id, "orgnr": orgnr}


# ── Analysis ──────────────────────────────────────────────────────────────────

@router.get("/portfolio/{portfolio_id}/risk")
def get_portfolio_risk(
    portfolio_id: int,
    svc: PortfolioService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    """Return risk summary for every company in the portfolio, sorted by risk score."""
    try:
        return svc.get_risk_summary(portfolio_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/portfolio/{portfolio_id}/ingest")
def ingest_portfolio(
    portfolio_id: int,
    svc: PortfolioService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Batch-fetch BRREG + financial data for all companies not yet in the database."""
    try:
        return svc.ingest_companies(portfolio_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/portfolio/{portfolio_id}/ingest/stream")
def stream_ingest_portfolio(portfolio_id: int, include_pdfs: bool = False):
    """Stream live NDJSON progress of portfolio ingest (Phase 1: BRREG, Phase 2: PDFs).

    Event types: start | searching | done | skipped | error | complete
                 pdf_searching | pdf_found | pdf_none | pdf_error
    """
    def generate():
        db = SessionLocal()
        try:
            yield from PortfolioService(db).stream_ingest(portfolio_id, include_pdfs)
        finally:
            db.close()

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.get("/portfolio/{portfolio_id}/seed-norway/stream")
def stream_seed_norway(portfolio_id: int):
    """Stream live NDJSON progress while seeding the portfolio with Norway's Top 100 companies."""
    def generate():
        db = SessionLocal()
        try:
            yield from PortfolioService(db).stream_seed_norway(portfolio_id)
        finally:
            db.close()

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.post("/portfolio/{portfolio_id}/enrich-pdfs")
def enrich_pdfs(
    portfolio_id: int,
    svc: PortfolioService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
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
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Answer a question grounded in the financial data of all companies in the portfolio."""
    try:
        return svc.chat(portfolio_id, body.question)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/portfolio/{portfolio_id}/analytics")
def get_portfolio_analytics(
    portfolio_id: int,
    svc: PortfolioService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Aggregate policy premium data for all companies in the portfolio."""
    try:
        return svc.get_analytics(portfolio_id, user.firm_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/portfolio/{portfolio_id}/alerts")
def get_portfolio_alerts(
    portfolio_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    """Detect significant YoY financial changes for companies in the portfolio."""
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return collect_alerts(portfolio_id, db)


@router.get("/portfolio/{portfolio_id}/concentration")
def get_portfolio_concentration(
    portfolio_id: int,
    svc: PortfolioService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Return portfolio concentration breakdown by industry, geography, and revenue size."""
    try:
        return svc.get_concentration(portfolio_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/portfolio/{portfolio_id}/pdf")
def download_portfolio_pdf(
    portfolio_id: int,
    svc: PortfolioService = Depends(_svc),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Generate and stream a portfolio report PDF."""
    from api.db import BrokerSettings
    from api.services.pdf_generate import generate_portfolio_pdf

    try:
        portfolio = svc.get(portfolio_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    orgnrs = [r.orgnr for r in db.query(PortfolioCompany).filter(PortfolioCompany.portfolio_id == portfolio_id).all()]
    companies = [
        {
            "orgnr": c.orgnr, "navn": c.navn, "omsetning": c.sum_driftsinntekter,
            "antall_ansatte": c.antall_ansatte, "egenkapitalandel": c.equity_ratio,
            "risk_score": c.risk_score, "kommune": c.kommune,
            "naeringskode1_beskrivelse": c.naeringskode1_beskrivelse,
        }
        for c in db.query(Company).filter(Company.orgnr.in_(orgnrs)).all()
    ]
    companies.sort(key=lambda x: (x.get("risk_score") or 0), reverse=True)
    alerts = collect_alerts(portfolio_id, db)
    concentration = svc.get_concentration(portfolio_id)
    settings = db.query(BrokerSettings).first()
    broker = {
        "firm_name": settings.firm_name if settings else "",
        "contact_name": settings.contact_name if settings else "",
        "contact_email": settings.contact_email if settings else "",
    }
    pdf_bytes = generate_portfolio_pdf(
        portfolio_name=portfolio.name,
        companies=companies,
        alerts=alerts,
        concentration=concentration,
        broker=broker,
    )
    filename = f"portefoeljerapport_{portfolio.name.replace(' ', '_')}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Batch CSV import ──────────────────────────────────────────────────────────

import csv
import io
import re

from fastapi import File, UploadFile, Query as _Query
from typing import Optional as _Optional

_MAX_IMPORT_ROWS = 500
_ORGNR_RE = re.compile(r"^\d{9}$")


def _parse_csv_orgnrs(content: bytes) -> tuple[list[str], list[str]]:
    """Parse CSV bytes → (valid_orgnrs, invalid_values). Deduplicates. Max 500 rows enforced outside."""
    text = content.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    col = next(
        (c for c in (reader.fieldnames or []) if "orgnr" in c.lower()),
        None,
    )
    # Restart reader if no orgnr header found — fall back to first column
    if col is None:
        reader = csv.reader(io.StringIO(text))  # type: ignore[assignment]
        rows = [r[0].strip() for r in reader if r and r[0].strip()]
    else:
        rows = [r.get(col, "").strip() for r in reader]

    seen, valid, invalid = set(), [], []
    for val in rows:
        if not val or val == col:
            continue
        if _ORGNR_RE.match(val):
            if val not in seen:
                seen.add(val)
                valid.append(val)
        else:
            invalid.append(val)
    return valid, invalid


@router.post("/batch/import")
async def batch_import_csv(
    file: UploadFile = File(...),
    portfolio_id: _Optional[int] = _Query(default=None),
):
    """Import orgnr values from a CSV file, fetch BRREG profiles, optionally add to a portfolio."""
    content = await file.read()
    valid, invalid_vals = _parse_csv_orgnrs(content)
    if len(valid) > _MAX_IMPORT_ROWS:
        raise HTTPException(status_code=422, detail=f"Maks {_MAX_IMPORT_ROWS} orgnr per import.")

    def generate():
        db = SessionLocal()
        try:
            yield from PortfolioService(db).stream_batch_import(portfolio_id, valid, invalid_count=len(invalid_vals))
        finally:
            db.close()

    return StreamingResponse(generate(), media_type="application/x-ndjson")
