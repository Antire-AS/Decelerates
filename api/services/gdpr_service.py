"""GDPR compliance service — soft-delete (Art. 17), data export (Art. 20), retention purge."""
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from api.db import (
    Company, CompanyHistory, CompanyNote, CompanyPdfSource, CompanyChunk,
    Policy, Claim, Activity,
)
from api.domain.exceptions import NotFoundError


_RETENTION_DAYS = 90  # hard-delete soft-deleted companies after this many days


class GdprService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def erase_company(self, orgnr: str) -> dict:
        """Soft-delete a company (GDPR Art. 17 — right to erasure).

        Sets deleted_at, clears PII-bearing fields (navn, pep_raw), and removes
        RAG chunks so the company no longer appears in AI answers.
        Returns a summary of what was erased.
        """
        company = self._get_company(orgnr)
        now = datetime.now(timezone.utc)
        company.deleted_at = now
        company.pep_raw = None  # PEP screening data is PII
        # Keep orgnr + financial figures (legitimate interest) but clear name
        company.navn = None

        # Remove RAG embeddings (may contain extracted PII from PDF reports)
        chunks_deleted = (
            self.db.query(CompanyChunk)
            .filter(CompanyChunk.orgnr == orgnr)
            .delete(synchronize_session=False)
        )
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"orgnr": orgnr, "deleted_at": now.isoformat(), "chunks_removed": chunks_deleted}

    def export_company_data(self, orgnr: str) -> dict[str, Any]:
        """Export all data held for a company (GDPR Art. 20 — data portability)."""
        company = self._get_company(orgnr)
        records = self._fetch_related_records(orgnr)
        return self._serialize_export(company, records)

    def _fetch_related_records(self, orgnr: str) -> dict:
        return {
            "history": (
                self.db.query(CompanyHistory)
                .filter(CompanyHistory.orgnr == orgnr)
                .order_by(CompanyHistory.year.desc()).all()
            ),
            "notes": (
                self.db.query(CompanyNote)
                .filter(CompanyNote.orgnr == orgnr)
                .order_by(CompanyNote.id.desc()).all()
            ),
            "sources": self.db.query(CompanyPdfSource).filter(CompanyPdfSource.orgnr == orgnr).all(),
            "policies": self.db.query(Policy).filter(Policy.orgnr == orgnr).all(),
            "claims": self.db.query(Claim).filter(Claim.orgnr == orgnr).all(),
            "activities": self.db.query(Activity).filter(Activity.orgnr == orgnr).all(),
        }

    @staticmethod
    def _serialize_export(company: "Company", r: dict) -> dict[str, Any]:
        return {
            "company": {
                "orgnr": company.orgnr,
                "navn": company.navn,
                "kommune": company.kommune,
                "naeringskode1_beskrivelse": company.naeringskode1_beskrivelse,
                "risk_score": company.risk_score,
                "deleted_at": company.deleted_at.isoformat() if company.deleted_at else None,
            },
            "financial_history": [
                {"year": h.year, "source": h.source, "sum_driftsinntekter": h.sum_driftsinntekter}
                for h in r["history"]
            ],
            "notes": [{"question": n.question, "answer": n.answer} for n in r["notes"]],
            "pdf_sources": [{"year": s.year, "pdf_url": s.pdf_url} for s in r["sources"]],
            "policies": [
                {"insurer": p.insurer, "product_type": p.product_type,
                 "renewal_date": p.renewal_date.isoformat() if p.renewal_date else None}
                for p in r["policies"]
            ],
            "claims": [{"claim_number": c.claim_number, "status": c.status.value} for c in r["claims"]],
            "activities": [
                {"subject": a.subject, "activity_type": a.activity_type.value} for a in r["activities"]
            ],
        }

    def purge_old_deletions(self) -> int:
        """Hard-delete companies soft-deleted more than _RETENTION_DAYS ago. Returns count."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=_RETENTION_DAYS)
        companies = (
            self.db.query(Company)
            .filter(Company.deleted_at.isnot(None), Company.deleted_at < cutoff)
            .all()
        )
        count = 0
        for company in companies:
            orgnr = company.orgnr
            for model in (CompanyChunk, CompanyNote, CompanyHistory, CompanyPdfSource):
                self.db.query(model).filter(model.orgnr == orgnr).delete(synchronize_session=False)
            self.db.delete(company)
            count += 1
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return count

    def _get_company(self, orgnr: str) -> Company:
        company = self.db.query(Company).filter(Company.orgnr == orgnr).first()
        if not company:
            raise NotFoundError(f"Company {orgnr} not found")
        return company
