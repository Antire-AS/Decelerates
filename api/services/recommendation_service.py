"""Recommendation letter service — creates, stores, and generates LLM rationale."""

# PEP 563 deferred annotation evaluation. Required because the RecommendationService
# class has a `list` method that shadows the builtin mid-class-body, which would
# otherwise break later `list[int]` annotations at class-definition time on
# Python <3.14 (no PEP 649 lazy annotations yet).
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from api.db import Recommendation, Submission, IddBehovsanalyse
from api.domain.exceptions import NotFoundError
from api.services.llm import _llm_answer_raw
import logging

logger = logging.getLogger(__name__)


def _build_rationale_prompt(
    company_name: str,
    orgnr: str,
    recommended_insurer: str,
    submissions: list,
    idd: Optional[IddBehovsanalyse],
) -> str:
    lines = [
        "Du er en erfaren forsikringsmegler. Skriv en kort faglig begrunnelse (3-5 avsnitt) på norsk",
        f"for hvorfor {recommended_insurer} er det beste valget for klienten {company_name} (org.nr {orgnr}).",
        "",
        "Begrunnelsen skal:",
        "- Forklare hvorfor det anbefalte selskapet passer klientens behov",
        "- Sammenligne kort med øvrige innhentede tilbud",
        "- Nevne pris, dekningsomfang og selskapets produktappetitt",
        "- Avslutte med en tydelig anbefaling",
        "",
    ]

    if idd:
        lines.append(f"Klientens risikoappetitt: {idd.risk_appetite or 'ikke oppgitt'}")
        lines.append(
            f"Anbefalte produkter fra behovsanalyse: {', '.join(idd.recommended_products or [])}"
        )
        lines.append("")

    if submissions:
        lines.append("Innhentede tilbud:")
        for s in submissions:
            status_map = {
                "quoted": "Tilbud mottatt",
                "declined": "Avslått",
                "pending": "Avventer",
                "withdrawn": "Trukket",
            }
            status_no = status_map.get(
                s.status.value if hasattr(s.status, "value") else s.status, s.status
            )
            premium = (
                f"{s.premium_offered_nok:,.0f} kr"
                if s.premium_offered_nok
                else "ikke oppgitt"
            )
            lines.append(
                f"- Produkt: {s.product_type} | Status: {status_no} | Premie: {premium} | Notater: {s.notes or '–'}"
            )
        lines.append("")

    lines.append(f"Anbefalt selskap: {recommended_insurer}")
    lines.append("Skriv begrunnelsen direkte, uten overskrifter.")
    return "\n".join(lines)


class RecommendationService:
    def __init__(self, db: Session):
        self.db = db

    def list(self, orgnr: str, firm_id: int) -> list[Recommendation]:
        return (
            self.db.query(Recommendation)
            .filter(Recommendation.orgnr == orgnr, Recommendation.firm_id == firm_id)
            .order_by(Recommendation.created_at.desc())
            .all()
        )

    def create(
        self,
        orgnr: str,
        firm_id: int,
        created_by_email: str,
        company_name: str,
        recommended_insurer: str,
        submission_ids: Optional[list[int]],
        idd_id: Optional[int],
        rationale_override: Optional[str],
    ) -> Recommendation:
        submissions = []
        if submission_ids:
            submissions = (
                self.db.query(Submission)
                .filter(
                    Submission.id.in_(submission_ids), Submission.firm_id == firm_id
                )
                .all()
            )

        idd = None
        if idd_id:
            idd = (
                self.db.query(IddBehovsanalyse)
                .filter(
                    IddBehovsanalyse.id == idd_id, IddBehovsanalyse.firm_id == firm_id
                )
                .first()
            )

        if rationale_override:
            rationale = rationale_override
        else:
            prompt = _build_rationale_prompt(
                company_name, orgnr, recommended_insurer, submissions, idd
            )
            rationale = _llm_answer_raw(prompt) or (
                f"{recommended_insurer} anbefales basert på innhentede tilbud og klientens forsikringsbehov."
            )

        row = Recommendation(
            orgnr=orgnr,
            firm_id=firm_id,
            created_by_email=created_by_email,
            created_at=datetime.now(timezone.utc),
            idd_id=idd_id,
            submission_ids=submission_ids or [],
            recommended_insurer=recommended_insurer,
            rationale_text=rationale,
        )
        self.db.add(row)
        try:
            self.db.commit()
            self.db.refresh(row)
        except Exception:
            self.db.rollback()
            raise
        return row

    def get(self, orgnr: str, firm_id: int, rec_id: int) -> Recommendation:
        return self._get_or_raise(orgnr, firm_id, rec_id)

    def store_pdf(self, rec_id: int, pdf_bytes: bytes) -> None:
        row = self.db.query(Recommendation).filter(Recommendation.id == rec_id).first()
        if row:
            row.pdf_content = pdf_bytes
            try:
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise

    def attach_signing_session(self, rec_id: int, session_id: str) -> None:
        """Plan §🟢 #11 — record the Signicat session id on a recommendation."""
        row = self.db.query(Recommendation).filter(Recommendation.id == rec_id).first()
        if row:
            row.signing_session_id = session_id
            try:
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise

    def mark_signed_by_session(
        self,
        session_id: str,
        signed_pdf_blob_url: Optional[str] = None,
    ) -> Optional[Recommendation]:
        """Plan §🟢 #11 — webhook handler. Updates by session_id (not rec_id)
        because Signicat only knows the session, never our internal id."""
        from datetime import datetime, timezone

        row = (
            self.db.query(Recommendation)
            .filter(Recommendation.signing_session_id == session_id)
            .first()
        )
        if not row:
            return None
        row.signed_at = datetime.now(timezone.utc)
        if signed_pdf_blob_url:
            row.signed_pdf_blob_url = signed_pdf_blob_url
        try:
            self.db.commit()
            self.db.refresh(row)
        except Exception:
            self.db.rollback()
            raise
        return row

    def delete(self, orgnr: str, firm_id: int, rec_id: int) -> None:
        row = self._get_or_raise(orgnr, firm_id, rec_id)
        self.db.delete(row)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _get_or_raise(self, orgnr: str, firm_id: int, rec_id: int) -> Recommendation:
        row = (
            self.db.query(Recommendation)
            .filter(
                Recommendation.id == rec_id,
                Recommendation.orgnr == orgnr,
                Recommendation.firm_id == firm_id,
            )
            .first()
        )
        if not row:
            raise NotFoundError(f"Recommendation {rec_id} not found")
        return row
