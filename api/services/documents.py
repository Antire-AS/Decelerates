"""InsuranceDocument and InsuranceOffer CRUD + LLM document analysis."""
import io
from datetime import datetime, timezone
from typing import List, Optional

import pdfplumber
from sqlalchemy.orm import Session

from api.db import InsuranceDocument, InsuranceOffer
from api.domain.exceptions import LlmUnavailableError
from api.services.llm import (
    _analyze_document_with_gemini,
    _compare_documents_with_gemini,
    _llm_answer_raw,
    _parse_json_from_llm_response,
)

_KEYPOINTS_PROMPT = (
    "Du er en norsk forsikringsekspert. Analyser dette forsikringsdokumentet grundig og trekk ut ALLE viktige punkter.\n\n"
    "Returner KUN gyldig JSON i dette eksakte formatet (alle lister skal ha 5-8 punkter der det er mulig):\n"
    '{\n'
    '  "om_dokumentet": "1-2 setninger: hva slags forsikring er dette, hvem er tilbyder/forsikringsselskap",\n'
    '  "hva_dekkes": ["dekning 1", "dekning 2", "dekning 3", "dekning 4", "dekning 5"],\n'
    '  "forsikringssum": "beløp eller grense for dekning",\n'
    '  "egenandel": "egenandelbeløp og eventuelle varianter",\n'
    '  "forsikringsperiode": "dekningsperiode (fra–til eller løpende)",\n'
    '  "viktige_vilkaar": ["vilkår 1", "vilkår 2", "vilkår 3", "vilkår 4", "vilkår 5"],\n'
    '  "unntak": ["unntak 1", "unntak 2", "unntak 3"],\n'
    '  "kontaktinfo": "skadenummer, kontaktperson eller nettside",\n'
    '  "sammendrag": "3-4 setninger som beskriver hva dokumentet dekker, hvem det gjelder for, og viktigste betingelser"\n'
    '}'
)


def _pdf_bytes_to_text(pdf_bytes: bytes) -> str:
    """Extract text from raw PDF bytes using pdfplumber (up to 40 pages)."""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages[:40])
    except Exception:
        return ""


def _build_compare_prompt(a: InsuranceDocument, b: InsuranceDocument) -> str:
    return (
        f"Du er en norsk forsikringsrådgiver som sammenligner to forsikringsdokumenter. "
        f"Svar alltid på norsk.\n\n"
        f"Dokument A: {a.title} ({a.insurer}, {a.year})\n"
        f"Dokument B: {b.title} ({b.insurer}, {b.year})\n\n"
        f"Returner KUN gyldig JSON (ingen markdown, ingen tekst utenfor JSON):\n"
        f'{{\n'
        f'  "doc_a_summary": "3-4 setninger om hva Dokument A dekker, for hvem og viktigste betingelser",\n'
        f'  "doc_b_summary": "3-4 setninger om hva Dokument B dekker, for hvem og viktigste betingelser",\n'
        f'  "pros_a": ["fordel 1", "fordel 2", "fordel 3"],\n'
        f'  "cons_a": ["ulempe 1", "ulempe 2"],\n'
        f'  "pros_b": ["fordel 1", "fordel 2", "fordel 3"],\n'
        f'  "cons_b": ["ulempe 1", "ulempe 2"],\n'
        f'  "comparison": [\n'
        f'    {{"area": "Dekningsomfang", "doc_a": "hva A sier", "doc_b": "hva B sier", "winner": "A|B|Lik"}}\n'
        f'  ],\n'
        f'  "conclusion": "Samlet konklusjon for forsikringstaker — 3-4 setninger"\n'
        f'}}\n\n'
        f'Inkluder i comparison: Dekningsomfang, Selvrisiko, Forsikringssum, Unntak/begrensninger, '
        f'Særlige vilkår, Forsikringsperiode. winner=A betyr A er bedre, B=B er bedre, Lik=ingen vesentlig forskjell.'
    )


class DocumentService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── InsuranceDocument ──────────────────────────────────────────────────────

    def store_document(
        self,
        pdf_bytes: bytes,
        filename: str,
        title: str,
        category: str,
        insurer: str,
        year: Optional[int],
        period: str,
        orgnr: Optional[str],
    ) -> InsuranceDocument:
        """Create and persist an InsuranceDocument. Returns the saved ORM row."""
        extracted = _pdf_bytes_to_text(pdf_bytes)
        doc = InsuranceDocument(
            title=title,
            category=category,
            insurer=insurer,
            year=year,
            period=period,
            orgnr=orgnr or None,
            filename=filename,
            pdf_content=pdf_bytes,
            extracted_text=extracted or None,
            uploaded_at=datetime.utcnow().isoformat(),
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def remove_document(self, doc_id: int) -> bool:
        """Delete an InsuranceDocument by ID. Returns True if found and deleted."""
        doc = self.db.query(InsuranceDocument).filter(InsuranceDocument.id == doc_id).first()
        if not doc:
            return False
        self.db.delete(doc)
        self.db.commit()
        return True

    def get_document_keypoints(self, doc: InsuranceDocument) -> dict:
        """Extract key points from an InsuranceDocument via text LLM or Gemini PDF fallback."""
        text = doc.extracted_text or ""
        if len(text) > 500:
            raw = _llm_answer_raw(f"{_KEYPOINTS_PROMPT}\n\nDokument:\n{text[:12000]}")
            if raw:
                parsed = _parse_json_from_llm_response(raw)
                if parsed:
                    return parsed

        raw = _analyze_document_with_gemini(doc.pdf_content, _KEYPOINTS_PROMPT)
        if raw:
            parsed = _parse_json_from_llm_response(raw)
            if parsed:
                return parsed

        return {
            "sammendrag": (text[:400] + "…") if text else "Ingen tekstinnhold tilgjengelig",
            "viktige_vilkaar": [],
            "unntak": [],
        }

    def answer_document_question(self, doc: InsuranceDocument, question: str) -> str:
        """Answer a question about an InsuranceDocument. Raises LlmUnavailableError if no LLM."""
        prompt = (
            f"Du er en norsk forsikringsrådgiver. Svar alltid på norsk. "
            f"Svar kun basert på innholdet i dette forsikringsdokumentet. "
            f"Vær presis og konkret. Oppgi sidetall eller avsnitt hvis relevant.\n\n"
            f"Spørsmål: {question}"
        )
        answer = _analyze_document_with_gemini(doc.pdf_content, prompt)
        if answer:
            return answer

        if doc.extracted_text is not None:
            fallback = (
                f"Du er en norsk forsikringsrådgiver. Svar alltid på norsk. "
                f"Svar kun basert på dette forsikringsdokumentets innhold:\n\n"
                f"{doc.extracted_text[:12000]}\n\nSpørsmål: {question}"
            )
            answer = _llm_answer_raw(fallback)
            if answer:
                return answer

        raise LlmUnavailableError("Ingen LLM tilgjengelig")

    def compare_two_documents(self, a: InsuranceDocument, b: InsuranceDocument) -> dict:
        """Compare two InsuranceDocuments using Gemini or text LLM. Raises LlmUnavailableError if no result."""
        prompt = _build_compare_prompt(a, b)
        text_a = str(a.extracted_text) if a.extracted_text else ""
        text_b = str(b.extracted_text) if b.extracted_text else ""

        if text_a and text_b:
            raw = _llm_answer_raw(
                f"{prompt}\n\n--- DOKUMENT A: {a.title} ---\n{text_a[:10000]}\n\n--- DOKUMENT B: {b.title} ---\n{text_b[:10000]}"
            )
            if raw:
                return _parse_json_from_llm_response(raw) or {"raw_text": raw}

        raw = _compare_documents_with_gemini(a.pdf_content, b.pdf_content, prompt)
        if raw:
            return _parse_json_from_llm_response(raw) or {"raw_text": raw}

        if text_a or text_b:
            raw = _llm_answer_raw(
                f"{prompt}\n\n--- DOKUMENT A: {a.title} ---\n{text_a[:8000]}\n\n--- DOKUMENT B: {b.title} ---\n{text_b[:8000]}"
            )
            if raw:
                return _parse_json_from_llm_response(raw) or {"raw_text": raw}

        raise LlmUnavailableError(
            "Ingen LLM tilgjengelig — legg til GEMINI_API_KEY eller ANTHROPIC_API_KEY i .env og restart appen"
        )

    # ── InsuranceOffer ─────────────────────────────────────────────────────────

    def save_offers(self, orgnr: str, offer_data: List[dict]) -> List[dict]:
        """Persist InsuranceOffer rows from pre-read file data.

        Each item in offer_data must have keys: filename, raw_bytes, extracted_text.
        Returns list of {"id", "filename", "insurer_name"}.
        """
        now = datetime.now(timezone.utc).isoformat()
        saved = []
        for item in offer_data:
            insurer_guess = (
                item["filename"].rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
            )
            row = InsuranceOffer(
                orgnr=orgnr,
                filename=item["filename"],
                insurer_name=insurer_guess,
                uploaded_at=now,
                pdf_content=item["raw_bytes"],
                extracted_text=item["extracted_text"],
            )
            self.db.add(row)
            self.db.flush()
            saved.append({"id": row.id, "filename": row.filename, "insurer_name": row.insurer_name})
        self.db.commit()
        return saved

    def remove_offer(self, offer_id: int, orgnr: str) -> bool:
        """Delete an InsuranceOffer by ID + orgnr. Returns True if found and deleted."""
        row = self.db.query(InsuranceOffer).filter(
            InsuranceOffer.id == offer_id, InsuranceOffer.orgnr == orgnr
        ).first()
        if not row:
            return False
        self.db.delete(row)
        self.db.commit()
        return True


# ── Module-level backward-compat wrappers ─────────────────────────────────────

def store_insurance_document(
    pdf_bytes: bytes, filename: str, title: str, category: str, insurer: str,
    year: Optional[int], period: str, orgnr: Optional[str], db: Session,
) -> InsuranceDocument:
    return DocumentService(db).store_document(pdf_bytes, filename, title, category, insurer, year, period, orgnr)


def remove_insurance_document(doc_id: int, db: Session) -> bool:
    return DocumentService(db).remove_document(doc_id)


def get_document_keypoints(doc: InsuranceDocument) -> dict:
    # No DB needed for read-only keypoint extraction; pass a no-op session
    return DocumentService(None).get_document_keypoints(doc)  # type: ignore[arg-type]


def answer_document_question(doc: InsuranceDocument, question: str) -> str:
    return DocumentService(None).answer_document_question(doc, question)  # type: ignore[arg-type]


def compare_two_documents(a: InsuranceDocument, b: InsuranceDocument) -> dict:
    return DocumentService(None).compare_two_documents(a, b)  # type: ignore[arg-type]


def save_insurance_offers(orgnr: str, offer_data: List[dict], db: Session) -> List[dict]:
    return DocumentService(db).save_offers(orgnr, offer_data)


def remove_insurance_offer(offer_id: int, orgnr: str, db: Session) -> bool:
    return DocumentService(db).remove_offer(offer_id, orgnr)
