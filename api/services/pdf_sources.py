"""CompanyPdfSource, CompanyHistory, and InsuranceDocument persistence helpers."""
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from api.db import CompanyPdfSource, CompanyHistory, InsuranceDocument


class PdfSourcesService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert_pdf_source(self, orgnr: str, year: int, url: str, label: str) -> CompanyPdfSource:
        """Insert or update a CompanyPdfSource row, uploading PDF to Azure Blob if configured."""
        from api.services.pdf_background import _upload_pdf_to_blob
        existing = (
            self.db.query(CompanyPdfSource)
            .filter(CompanyPdfSource.orgnr == orgnr, CompanyPdfSource.year == year)
            .first()
        )
        if not existing:
            existing = CompanyPdfSource(orgnr=orgnr, year=year)
            self.db.add(existing)
        existing.pdf_url = url
        existing.label = label
        existing.added_at = datetime.now(timezone.utc).isoformat()
        # Upload to blob if not already stored (skip re-upload on subsequent upserts)
        if not getattr(existing, "blob_url", None):
            existing.blob_url = _upload_pdf_to_blob(url, orgnr, year, label)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return existing

    def save_insurance_document(
        self, orgnr: str, navn: str, filename: str, pdf_bytes: bytes
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
        self.db.add(doc)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return doc

    def delete_history_year(self, orgnr: str) -> int:
        """Delete all CompanyHistory rows for *orgnr*. Returns deleted row count."""
        deleted = (
            self.db.query(CompanyHistory)
            .filter(CompanyHistory.orgnr == orgnr)
            .delete()
        )
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return deleted


# ── Module-level helpers (backward-compatible, used by company.py and risk_router.py) ──

def upsert_pdf_source(orgnr: str, year: int, url: str, label: str, db: Session) -> CompanyPdfSource:
    return PdfSourcesService(db).upsert_pdf_source(orgnr, year, url, label)


def save_insurance_document(
    orgnr: str, navn: str, filename: str, pdf_bytes: bytes, db: Session
) -> InsuranceDocument:
    return PdfSourcesService(db).save_insurance_document(orgnr, navn, filename, pdf_bytes)


def delete_history_year(orgnr: str, db: Session) -> int:
    return PdfSourcesService(db).delete_history_year(orgnr)
