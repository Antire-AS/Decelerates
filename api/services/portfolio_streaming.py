"""Portfolio streaming — NDJSON event generators for live ingest progress."""
import json
import logging
from datetime import datetime, timezone
from threading import Thread
from typing import Iterator

from sqlalchemy.orm import Session

from api.db import PortfolioCompany, Company, CompanyPdfSource, SessionLocal
from api.services.company import fetch_org_profile
from api.services.external_apis import fetch_enhetsregisteret, fetch_enhet_by_orgnr
from api.services.pdf_extract import _run_phase2_discovery, _extract_pending_sources

logger = logging.getLogger(__name__)


def _stream_pdf_phase(pc, navn: str, i: int, total: int, db: Session) -> Iterator[str]:
    """Phase 2: discover PDFs for one company and yield NDJSON events."""
    from datetime import datetime as _dt

    current_year = _dt.now().year
    covered = {s.year for s in db.query(CompanyPdfSource).filter(CompanyPdfSource.orgnr == pc.orgnr).all()}
    missing = [y for y in range(current_year - 4, current_year + 1) if y not in covered]
    if not missing:
        yield json.dumps({"type": "pdf_found", "orgnr": pc.orgnr, "navn": navn, "found_years": sorted(covered), "new": False, "index": i, "total": total}) + "\n"
        return
    yield json.dumps({"type": "pdf_searching", "orgnr": pc.orgnr, "navn": navn, "missing_years": missing, "index": i, "total": total}) + "\n"
    try:
        org = fetch_enhet_by_orgnr(pc.orgnr) or {"navn": navn, "organisasjonsnummer": pc.orgnr}
        sources = _run_phase2_discovery(pc.orgnr, org, db)
        found_years = sorted({s.year for s in sources})
        new_years = [y for y in found_years if y in missing]
        if new_years:
            yield json.dumps({"type": "pdf_found", "orgnr": pc.orgnr, "navn": navn, "found_years": found_years, "new_years": new_years, "new": True, "index": i, "total": total}) + "\n"
            Thread(target=_extract_pending_sources, args=(pc.orgnr, sources, SessionLocal()), daemon=True).start()
        else:
            yield json.dumps({"type": "pdf_none", "orgnr": pc.orgnr, "navn": navn, "index": i, "total": total}) + "\n"
    except Exception as exc:
        yield json.dumps({"type": "pdf_error", "orgnr": pc.orgnr, "navn": navn, "error": str(exc)[:120], "index": i, "total": total}) + "\n"


def _stream_ingest_company(pc, i: int, total: int, include_pdfs: bool, db: Session) -> Iterator[str]:
    """Stream BRREG + optional PDF events for one portfolio company."""
    existing = db.query(Company).filter(Company.orgnr == pc.orgnr).first()
    navn = (existing.navn if existing else None) or pc.orgnr
    if existing and existing.navn and existing.risk_score is not None:
        yield json.dumps({"type": "skipped", "orgnr": pc.orgnr, "navn": navn, "risk_score": existing.risk_score, "index": i, "total": total}) + "\n"
        return
    yield json.dumps({"type": "searching", "orgnr": pc.orgnr, "navn": navn, "index": i, "total": total}) + "\n"
    try:
        fetch_org_profile(pc.orgnr, db)
        company = db.query(Company).filter(Company.orgnr == pc.orgnr).first()
        navn = company.navn if company else navn
        yield json.dumps({"type": "done", "orgnr": pc.orgnr, "navn": navn, "risk_score": company.risk_score if company else None, "index": i, "total": total}) + "\n"
    except Exception as exc:
        yield json.dumps({"type": "error", "orgnr": pc.orgnr, "navn": navn, "error": str(exc)[:120], "index": i, "total": total}) + "\n"
        return
    if include_pdfs:
        yield from _stream_pdf_phase(pc, navn, i, total, db)


def stream_ingest(portfolio_id: int, include_pdfs: bool, db: Session) -> Iterator[str]:
    """Stream NDJSON progress events for portfolio ingest (BRREG + optional PDFs)."""
    rows = db.query(PortfolioCompany).filter(PortfolioCompany.portfolio_id == portfolio_id).all()
    total = len(rows)
    yield json.dumps({"type": "start", "total": total, "include_pdfs": include_pdfs}) + "\n"
    for i, pc in enumerate(rows):
        yield from _stream_ingest_company(pc, i + 1, total, include_pdfs, db)
    yield json.dumps({"type": "complete", "total": total}) + "\n"


def stream_seed_norway(portfolio_id: int, db: Session) -> Iterator[str]:
    """Stream NDJSON events while adding Norway Top 100 companies to the portfolio."""
    from api.constants import TOP_100_NO_NAMES

    existing = {pc.orgnr for pc in db.query(PortfolioCompany).filter(PortfolioCompany.portfolio_id == portfolio_id).all()}
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
            orgnr, found_name = results[0]["orgnr"], results[0]["navn"]
            if orgnr in existing:
                yield json.dumps({"type": "skipped", "name": found_name, "orgnr": orgnr, "index": i + 1, "total": total}) + "\n"
                skipped += 1
                continue
            db.add(PortfolioCompany(portfolio_id=portfolio_id, orgnr=orgnr, added_at=datetime.now(timezone.utc).isoformat()))
            db.commit()
            existing.add(orgnr)
            yield json.dumps({"type": "added", "name": found_name, "orgnr": orgnr, "index": i + 1, "total": total}) + "\n"
            added += 1
        except Exception as exc:
            yield json.dumps({"type": "error", "name": name, "error": str(exc)[:100], "index": i + 1, "total": total}) + "\n"
            not_found += 1
    yield json.dumps({"type": "complete", "added": added, "skipped": skipped, "not_found": not_found}) + "\n"


def stream_batch_import(portfolio_id: int | None, orgnrs: list[str], invalid_count: int, db: Session) -> Iterator[str]:
    """Stream NDJSON progress while importing companies from a list of orgnrs."""
    from api.services import fetch_org_profile

    total = len(orgnrs)
    yield json.dumps({"type": "start", "total": total, "invalid": invalid_count}) + "\n"
    added, failed = 0, 0
    for i, orgnr in enumerate(orgnrs):
        yield json.dumps({"type": "searching", "orgnr": orgnr, "index": i + 1, "total": total}) + "\n"
        try:
            result = fetch_org_profile(orgnr, db)
            navn = (result or {}).get("org", {}).get("navn", orgnr) if result else orgnr
            if portfolio_id:
                db.merge(PortfolioCompany(portfolio_id=portfolio_id, orgnr=orgnr, added_at=datetime.now(timezone.utc).isoformat()))
                db.commit()
            yield json.dumps({"type": "done", "orgnr": orgnr, "navn": navn, "index": i + 1, "total": total}) + "\n"
            added += 1
        except Exception as exc:
            yield json.dumps({"type": "error", "orgnr": orgnr, "error": str(exc)[:120], "index": i + 1, "total": total}) + "\n"
            failed += 1
    yield json.dumps({"type": "complete", "added": added, "failed": failed, "invalid": invalid_count}) + "\n"
