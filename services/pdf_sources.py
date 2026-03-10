"""CompanyPdfSource, CompanyHistory, and InsuranceDocument persistence helpers."""
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from db import CompanyPdfSource, CompanyHistory, InsuranceDocument


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


def save_insurance_document(
    orgnr: str, navn: str, filename: str, pdf_bytes: bytes, db: Session
) -> InsuranceDocument:
    """Persist a generated insurance offer PDF as an InsuranceDocument row."""
    doc = InsuranceDocument(
        title=f"Forsikringstilbud — {navn}",
        category="anbefaling",
        insurer="AI-generert",
        year=date.today().year,
        period="aktiv",
        orgnr=orgnr,
        filename=filename,
        pdf_content=pdf_bytes,
        extracted_text=None,
        uploaded_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(doc)
    db.commit()
    return doc


def delete_history_year(orgnr: str, db: Session) -> int:
    """Delete all CompanyHistory rows for *orgnr*. Returns deleted row count."""
    deleted = (
        db.query(CompanyHistory)
        .filter(CompanyHistory.orgnr == orgnr)
        .delete()
    )
    db.commit()
    return deleted
