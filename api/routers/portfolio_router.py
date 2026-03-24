"""Portfolio endpoints — named company lists with risk analysis and cross-company chat."""
import json

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.db import PortfolioCompany, Company, Portfolio
from api.db import SessionLocal
from api.dependencies import get_db
from api.domain.exceptions import NotFoundError
from api.limiter import limiter
from api.schemas import PortfolioCreate, PortfolioAddCompany, ChatRequest
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
    """Stream live progress of portfolio ingest as newline-delimited JSON.

    Phase 1 (always): BRREG + risk score per company — fast, ~1-2s each.
    Phase 2 (include_pdfs=true): Claude web-searches each company's investor
    relations site to find annual + quarterly report PDFs, then extracts
    5 years of financials. Takes 20-60s per company — best for demos of ≤20 companies.

    Event types:
      start | searching | done | skipped | error | complete
      pdf_searching | pdf_found | pdf_none | pdf_error
    """
    def generate():
        from api.services.company import fetch_org_profile
        from api.services.external_apis import fetch_enhet_by_orgnr

        db = SessionLocal()
        try:
            rows = db.query(PortfolioCompany).filter(PortfolioCompany.portfolio_id == portfolio_id).all()
            total = len(rows)
            yield json.dumps({"type": "start", "total": total, "include_pdfs": include_pdfs}) + "\n"

            for i, pc in enumerate(rows):
                existing = db.query(Company).filter(Company.orgnr == pc.orgnr).first()
                navn = (existing.navn if existing else None) or pc.orgnr

                # ── Phase 1: BRREG + risk ──────────────────────────────────
                if existing and existing.navn and existing.risk_score is not None:
                    yield json.dumps({
                        "type": "skipped", "orgnr": pc.orgnr, "navn": navn,
                        "risk_score": existing.risk_score, "index": i + 1, "total": total,
                    }) + "\n"
                else:
                    yield json.dumps({
                        "type": "searching", "orgnr": pc.orgnr, "navn": navn,
                        "index": i + 1, "total": total,
                    }) + "\n"
                    try:
                        fetch_org_profile(pc.orgnr, db)
                        company = db.query(Company).filter(Company.orgnr == pc.orgnr).first()
                        navn = (company.navn if company else navn)
                        yield json.dumps({
                            "type": "done", "orgnr": pc.orgnr, "navn": navn,
                            "risk_score": (company.risk_score if company else None),
                            "index": i + 1, "total": total,
                        }) + "\n"
                    except Exception as exc:
                        yield json.dumps({
                            "type": "error", "orgnr": pc.orgnr, "navn": navn,
                            "error": str(exc)[:120], "index": i + 1, "total": total,
                        }) + "\n"
                        continue

                if not include_pdfs:
                    continue

                # ── Phase 2: web-search for PDFs on company website ────────
                from datetime import datetime
                from api.db import CompanyPdfSource
                from api.services.pdf_extract import _run_phase2_discovery

                current_year = datetime.now().year
                target_years = list(range(current_year - 4, current_year + 1))
                covered = {
                    s.year for s in
                    db.query(CompanyPdfSource).filter(CompanyPdfSource.orgnr == pc.orgnr).all()
                }
                missing = [y for y in target_years if y not in covered]

                if not missing:
                    yield json.dumps({
                        "type": "pdf_found", "orgnr": pc.orgnr, "navn": navn,
                        "found_years": sorted(covered), "new": False,
                        "index": i + 1, "total": total,
                    }) + "\n"
                    continue

                yield json.dumps({
                    "type": "pdf_searching", "orgnr": pc.orgnr, "navn": navn,
                    "missing_years": missing, "index": i + 1, "total": total,
                }) + "\n"

                try:
                    org = fetch_enhet_by_orgnr(pc.orgnr) or {"navn": navn, "organisasjonsnummer": pc.orgnr}
                    sources = _run_phase2_discovery(pc.orgnr, org, db)
                    found_years = sorted({s.year for s in sources})
                    new_years = [y for y in found_years if y in missing]

                    if new_years:
                        yield json.dumps({
                            "type": "pdf_found", "orgnr": pc.orgnr, "navn": navn,
                            "found_years": found_years, "new_years": new_years,
                            "new": True, "index": i + 1, "total": total,
                        }) + "\n"
                        # Kick off extraction in background (non-blocking)
                        from threading import Thread
                        from api.services.pdf_extract import _extract_pending_sources
                        t = Thread(
                            target=_extract_pending_sources,
                            args=(pc.orgnr, sources, SessionLocal()),
                            daemon=True,
                        )
                        t.start()
                    else:
                        yield json.dumps({
                            "type": "pdf_none", "orgnr": pc.orgnr, "navn": navn,
                            "index": i + 1, "total": total,
                        }) + "\n"
                except Exception as exc:
                    yield json.dumps({
                        "type": "pdf_error", "orgnr": pc.orgnr, "navn": navn,
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
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Return portfolio concentration breakdown by industry, geography, and revenue size."""
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    from api.constants import _NACE_SECTION_MAP, NACE_BENCHMARKS
    orgnrs = [
        r.orgnr for r in
        db.query(PortfolioCompany).filter(PortfolioCompany.portfolio_id == portfolio_id).all()
    ]
    companies = db.query(Company).filter(Company.orgnr.in_(orgnrs)).all()

    def _section(nace):
        if not nace:
            return "?"
        try:
            code = int(str(nace).split(".")[0])
            for rng, s in _NACE_SECTION_MAP:
                if code in rng:
                    return s
        except (ValueError, AttributeError):
            pass
        return "?"

    def _rev_band(rev):
        if not rev:
            return "Ukjent"
        if rev < 10_000_000:
            return "<10 MNOK"
        if rev < 100_000_000:
            return "10–100 MNOK"
        if rev < 1_000_000_000:
            return "100 MNOK–1 BNOK"
        return ">1 BNOK"

    industry: dict[str, dict] = {}
    geography: dict[str, int] = {}
    size: dict[str, int] = {}
    total_revenue = 0.0

    for c in companies:
        sec = _section(c.naeringskode1)
        label = NACE_BENCHMARKS.get(sec, {}).get("industry", sec)
        industry.setdefault(sec, {"section": sec, "label": label, "count": 0, "revenue": 0})
        industry[sec]["count"] += 1
        industry[sec]["revenue"] += c.sum_driftsinntekter or 0

        kom = c.kommune or "Ukjent"
        geography[kom] = geography.get(kom, 0) + 1

        band = _rev_band(c.sum_driftsinntekter)
        size[band] = size.get(band, 0) + 1
        total_revenue += c.sum_driftsinntekter or 0

    geo_sorted = sorted(geography.items(), key=lambda x: x[1], reverse=True)[:10]
    return {
        "portfolio_id": portfolio_id,
        "total_companies": len(companies),
        "total_revenue": total_revenue,
        "by_industry": sorted(industry.values(), key=lambda x: x["count"], reverse=True),
        "by_geography": [{"kommune": k, "count": v} for k, v in geo_sorted],
        "by_size": [{"band": k, "count": v} for k, v in size.items()],
    }


@router.get("/portfolio/{portfolio_id}/pdf")
def download_portfolio_pdf(
    portfolio_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Generate and stream a portfolio report PDF."""
    from api.db import BrokerSettings
    from api.services.pdf_generate import generate_portfolio_pdf

    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    orgnrs = [
        r.orgnr for r in
        db.query(PortfolioCompany).filter(PortfolioCompany.portfolio_id == portfolio_id).all()
    ]
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

    concentration = get_portfolio_concentration(portfolio_id, db)

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
        from datetime import datetime, timezone
        from api.services import fetch_org_profile

        db = SessionLocal()
        total = len(valid)
        try:
            yield json.dumps({"type": "start", "total": total, "invalid": len(invalid_vals)}) + "\n"
            added, failed = 0, 0
            for i, orgnr in enumerate(valid):
                yield json.dumps({"type": "searching", "orgnr": orgnr, "index": i + 1, "total": total}) + "\n"
                try:
                    result = fetch_org_profile(orgnr, db)
                    navn = (result or {}).get("org", {}).get("navn", orgnr) if result else orgnr
                    if portfolio_id:
                        db.merge(PortfolioCompany(
                            portfolio_id=portfolio_id,
                            orgnr=orgnr,
                            added_at=datetime.now(timezone.utc).isoformat(),
                        ))
                        db.commit()
                    yield json.dumps({"type": "done", "orgnr": orgnr, "navn": navn, "index": i + 1, "total": total}) + "\n"
                    added += 1
                except Exception as exc:
                    yield json.dumps({"type": "error", "orgnr": orgnr, "error": str(exc)[:120], "index": i + 1, "total": total}) + "\n"
                    failed += 1
            yield json.dumps({"type": "complete", "added": added, "failed": failed, "invalid": len(invalid_vals)}) + "\n"
        finally:
            db.close()

    return StreamingResponse(generate(), media_type="application/x-ndjson")
