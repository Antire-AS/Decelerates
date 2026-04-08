"""PDF history — DB upsert and merged history retrieval."""
import logging
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from api.db import CompanyHistory
from api.domain.exceptions import PdfExtractionError
from api.services.external_apis import fetch_regnskap_history
from api.services.pdf_parse import _parse_financials_from_pdf

logger = logging.getLogger(__name__)


def _upsert_history_row(existing: Any, parsed: Dict[str, Any], pdf_url: str) -> None:
    """Copy parsed financial fields onto an existing CompanyHistory ORM object."""
    existing.source = "pdf"
    existing.pdf_url = pdf_url
    existing.revenue = parsed.get("revenue")
    existing.net_result = parsed.get("net_result")
    existing.equity = parsed.get("equity")
    existing.total_assets = parsed.get("total_assets")
    existing.equity_ratio = parsed.get("equity_ratio")
    existing.short_term_debt = parsed.get("short_term_debt")
    existing.long_term_debt = parsed.get("long_term_debt")
    existing.antall_ansatte = parsed.get("antall_ansatte")
    existing.currency = parsed.get("currency", "NOK")
    existing.raw = parsed


def fetch_history_from_pdf(
    orgnr: str, pdf_url: str, year: int, label: str, db: Session
) -> Dict[str, Any]:
    """Parse financials from PDF and upsert into company_history."""
    parsed = _parse_financials_from_pdf(pdf_url, orgnr, year)
    if not parsed:
        raise PdfExtractionError(f"Could not parse financials from PDF: {pdf_url}")

    existing = (
        db.query(CompanyHistory)
        .filter(CompanyHistory.orgnr == orgnr, CompanyHistory.year == year)
        .first()
    )
    if not existing:
        existing = CompanyHistory(orgnr=orgnr, year=year)
        db.add(existing)

    _upsert_history_row(existing, parsed, pdf_url)
    db.commit()

    return {
        "year": year,
        "source": "pdf",
        "pdf_url": pdf_url,
        "label": label,
        "currency": existing.currency,
        "revenue": existing.revenue,
        "net_result": existing.net_result,
        "equity": existing.equity,
        "total_assets": existing.total_assets,
        "equity_ratio": existing.equity_ratio,
        "short_term_debt": existing.short_term_debt,
        "long_term_debt": existing.long_term_debt,
        "antall_ansatte": existing.antall_ansatte,
    }


def _get_full_history(orgnr: str, db: Session) -> List[Dict[str, Any]]:
    """Return merged history: DB rows (PDF/manual) + BRREG, deduped by year, sorted desc."""
    db_rows = (
        db.query(CompanyHistory)
        .filter(CompanyHistory.orgnr == orgnr)
        .order_by(CompanyHistory.year.desc())
        .all()
    )
    by_year: Dict[int, Dict[str, Any]] = {}
    for row in db_rows:
        base = dict(row.raw) if row.raw else {}
        base.update({
            "year": row.year,
            "source": row.source,
            "currency": row.currency or "NOK",
            "revenue": row.revenue,
            "net_result": row.net_result,
            "equity": row.equity,
            "total_assets": row.total_assets,
            "equity_ratio": row.equity_ratio,
            "short_term_debt": row.short_term_debt,
            "long_term_debt": row.long_term_debt,
            "antall_ansatte": row.antall_ansatte,
        })
        by_year[row.year] = base

    try:
        brreg_rows = fetch_regnskap_history(orgnr)
    except Exception:
        brreg_rows = []

    for row in brreg_rows:
        year = row.get("year")
        if year and year not in by_year:
            by_year[year] = {**row, "source": "brreg", "currency": "NOK"}

    return sorted(by_year.values(), key=lambda r: r["year"], reverse=True)
