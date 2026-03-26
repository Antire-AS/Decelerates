"""PDF background tasks — URL validation, phase-2 discovery, parallel extraction, service class."""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import requests
from sqlalchemy.orm import Session

from api.db import CompanyHistory, CompanyPdfSource, SessionLocal
from api.services.pdf_agents import _agent_discover_pdfs, _discover_ir_pdfs
from api.services.pdf_history import fetch_history_from_pdf, _get_full_history
from api.services.pdf_parse import _parse_financials_from_pdf
from api.services.pdf_web import _DDG_UA

logger = logging.getLogger(__name__)


def _validate_pdf_urls(discovered: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter discovered PDF items to those reachable via HTTP HEAD (status < 400)."""
    valid = []
    for item in discovered:
        url = item.get("pdf_url", "")
        try:
            r = requests.head(url, timeout=10, allow_redirects=True,
                              headers={"User-Agent": _DDG_UA})
            if r.status_code < 400:
                valid.append(item)
                logger.info("[discovery] URL OK (%s): %s", r.status_code, url)
            else:
                logger.warning("[discovery] URL %s returned %s — skipping", url, r.status_code)
        except Exception as exc:
            logger.warning("[discovery] URL check failed for %s: %s — skipping", url, exc)
    return valid


def _run_phase2_discovery(orgnr: str, org: Dict[str, Any], db: Session) -> List[Any]:
    """Discover and cache IR PDFs for *orgnr* via agent + DuckDuckGo fallback."""
    navn = org.get("navn", "")
    hjemmeside = org.get("hjemmeside")
    current_year = datetime.now().year
    target_years = [current_year - i for i in range(1, 6)]

    logger.info("[discovery] Phase 2 starting for %s (%s), homepage=%s", navn, orgnr, hjemmeside)
    discovered = _agent_discover_pdfs(orgnr, navn, hjemmeside, target_years)
    if not discovered:
        logger.info("[discovery] Agent found nothing — falling back to DuckDuckGo for %s", orgnr)
        discovered = _discover_ir_pdfs(orgnr, navn, hjemmeside, target_years)

    discovered = _validate_pdf_urls(discovered)
    logger.info("[discovery] Phase 2 validated %d PDF sources for %s", len(discovered), orgnr)
    for item in discovered:
        existing = (
            db.query(CompanyPdfSource)
            .filter(
                CompanyPdfSource.orgnr == orgnr,
                CompanyPdfSource.year == item["year"],
            )
            .first()
        )
        if not existing:
            db.add(CompanyPdfSource(
                orgnr=orgnr,
                year=item["year"],
                pdf_url=item["pdf_url"],
                label=item.get("label", ""),
                added_at=datetime.now(timezone.utc).isoformat(),
            ))
    if discovered:
        db.commit()

    return db.query(CompanyPdfSource).filter(CompanyPdfSource.orgnr == orgnr).all()


def _extract_pending_sources(orgnr: str, sources: List[Any], db: Session) -> None:
    """Extract financials for any PDF sources not yet in company_history.

    Runs up to 3 extractions in parallel — each in its own DB session so
    SQLAlchemy sessions are never shared across threads.
    """
    pending = [
        src for src in sources
        if not db.query(CompanyHistory).filter(
            CompanyHistory.orgnr == orgnr,
            CompanyHistory.year == src.year,
        ).first()
    ]

    if not pending:
        return

    def _extract_one(src: Any) -> None:
        thread_db = SessionLocal()
        try:
            logger.info("[extract] Extracting financials from %s (year=%s)", src.pdf_url, src.year)
            fetch_history_from_pdf(orgnr, src.pdf_url, src.year, src.label or "", thread_db)
            logger.info("[extract] Done: %s year=%s", orgnr, src.year)
        except Exception as exc:
            logger.error("[extract] Failed for %s year=%s: %s", orgnr, src.year, exc)
        finally:
            thread_db.close()

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_extract_one, src): src for src in pending}
        for f in as_completed(futures):
            f.result()


def _auto_extract_pdf_sources(
    orgnr: str,
    org: Optional[Dict[str, Any]] = None,
    db_factory: Callable[[], Session] = SessionLocal,
) -> None:
    """Background task: Phase 1 seeds + Phase 2 IR discovery fallback.

    Accepts *db_factory* so tests can inject a mock session factory.
    """
    logger.info("[bg] _auto_extract_pdf_sources started for %s", orgnr)
    db = db_factory()
    try:
        sources = db.query(CompanyPdfSource).filter(CompanyPdfSource.orgnr == orgnr).all()

        current_year = datetime.now().year
        target_years = set(range(current_year - 5, current_year))
        covered_years = {s.year for s in sources}
        missing = target_years - covered_years
        needs_discovery = len(missing) >= 3
        logger.info(
            "[bg] %s: covered=%s, missing=%s, needs_discovery=%s",
            orgnr, sorted(covered_years), sorted(missing), needs_discovery,
        )

        if needs_discovery and org:
            sources = _run_phase2_discovery(orgnr, org, db)
        elif needs_discovery and not org:
            logger.warning("[bg] %s needs discovery but org dict not provided — skipping", orgnr)

        _extract_pending_sources(orgnr, sources, db)
        logger.info("[bg] _auto_extract_pdf_sources done for %s", orgnr)
    except Exception as exc:
        logger.error("[bg] _auto_extract_pdf_sources error for %s: %s", orgnr, exc, exc_info=True)
    finally:
        db.close()


# ── Service class wrapper ──────────────────────────────────────────────────────

class PdfExtractService:
    """Thin class wrapper around module-level PDF extraction helpers."""

    def __init__(self, db) -> None:
        self.db = db

    def fetch_history_from_pdf(self, orgnr: str, pdf_url: str, year: int, label: str):
        return fetch_history_from_pdf(orgnr, pdf_url, year, label, self.db)

    def get_full_history(self, orgnr: str):
        return _get_full_history(orgnr, self.db)

    def parse_financials_from_pdf(self, pdf_url: str, orgnr: str, year: int):
        return _parse_financials_from_pdf(pdf_url, orgnr, year)
