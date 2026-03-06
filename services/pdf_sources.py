"""CompanyPdfSource and CompanyHistory persistence helpers."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from db import CompanyPdfSource, CompanyHistory


def upsert_pdf_source(orgnr: str, year: int, url: str, label: str, db: Session) -> CompanyPdfSource:
    """Insert or update a CompanyPdfSource row."""
    existing = (
        db.query(CompanyPdfSource)
        .filter(CompanyPdfSource.orgnr == orgnr, CompanyPdfSource.year == year)
        .first()
    )
    if not existing:
        existing = CompanyPdfSource(orgnr=orgnr, year=year)
        db.add(existing)
    existing.pdf_url = url
    existing.label = label
    existing.added_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    return existing


def delete_history_year(orgnr: str, db: Session) -> int:
    """Delete all CompanyHistory rows for *orgnr*. Returns deleted row count."""
    deleted = (
        db.query(CompanyHistory)
        .filter(CompanyHistory.orgnr == orgnr)
        .delete()
    )
    db.commit()
    return deleted
