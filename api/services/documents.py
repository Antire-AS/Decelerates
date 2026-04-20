"""InsuranceDocument and InsuranceOffer CRUD + LLM document analysis."""

import io
from datetime import datetime, timezone
from typing import List, Optional

import pdfplumber
from sqlalchemy.orm import Session

from api.constants import (
    LLM_DOCUMENT_CHAR_LIMIT,
    LLM_TEXT_CHAR_LIMIT,
    PDF_PAGE_LIMIT_LAYOUT,
    TEXT_EMBED_CHAR_LIMIT,
)
from api.db import InsuranceDocument, InsuranceOffer
from api.domain.exceptions import LlmUnavailableError
from api.services.llm import (
    _analyze_document_with_gemini,
    _compare_documents_with_gemini,
    _embed,
    _llm_answer_raw,
    _parse_json_from_llm_response,
)

_KEYPOINTS_PROMPT = (
    "Du er en norsk forsikringsekspert. Analyser dette forsikringsdokumentet grundig og trekk ut ALLE viktige punkter.\n\n"
    "Returner KUN gyldig JSON i dette eksakte formatet (alle lister skal ha 5-8 punkter der det er mulig):\n"
    "{\n"
    '  "om_dokumentet": "1-2 setninger: hva slags forsikring er dette, hvem er tilbyder/forsikringsselskap",\n'
    '  "hva_dekkes": ["dekning 1", "dekning 2", "dekning 3", "dekning 4", "dekning 5"],\n'
    '  "forsikringssum": "beløp eller grense for dekning",\n'
    '  "egenandel": "egenandelbeløp og eventuelle varianter",\n'
    '  "forsikringsperiode": "dekningsperiode (fra–til eller løpende)",\n'
    '  "viktige_vilkaar": ["vilkår 1", "vilkår 2", "vilkår 3", "vilkår 4", "vilkår 5"],\n'
    '  "unntak": ["unntak 1", "unntak 2", "unntak 3"],\n'
    '  "kontaktinfo": "skadenummer, kontaktperson eller nettside",\n'
    '  "sammendrag": "3-4 setninger som beskriver hva dokumentet dekker, hvem det gjelder for, og viktigste betingelser"\n'
    "}"
)


def _cosine_similarity(a: list, b: list) -> float:
    """Return cosine similarity in [0, 1] between two embedding vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def _pdf_bytes_to_text(pdf_bytes: bytes) -> str:
    """Extract text from raw PDF bytes using pdfplumber (up to PDF_PAGE_LIMIT_LAYOUT pages)."""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            return "\n".join(
                p.extract_text() or "" for p in pdf.pages[:PDF_PAGE_LIMIT_LAYOUT]
            )
    except Exception:
        return ""


def _validate_pdf(pdf_bytes: bytes) -> bool:
    """Return True if pdf_bytes is a valid, non-empty PDF."""
    if not pdf_bytes or pdf_bytes[:5] != b"%PDF-":
        return False
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            return len(pdf.pages) > 0
    except Exception:
        return False


def _build_compare_prompt(a: InsuranceDocument, b: InsuranceDocument) -> str:
    return (
        f"Du er en norsk forsikringsrådgiver som sammenligner to forsikringsdokumenter. "
        f"Svar alltid på norsk.\n\n"
        f"Dokument A: {a.title} ({a.insurer}, {a.year})\n"
        f"Dokument B: {b.title} ({b.insurer}, {b.year})\n\n"
        f"Returner KUN gyldig JSON (ingen markdown, ingen tekst utenfor JSON):\n"
        f"{{\n"
        f'  "doc_a_summary": "3-4 setninger om hva Dokument A dekker, for hvem og viktigste betingelser",\n'
        f'  "doc_b_summary": "3-4 setninger om hva Dokument B dekker, for hvem og viktigste betingelser",\n'
        f'  "pros_a": ["fordel 1", "fordel 2", "fordel 3"],\n'
        f'  "cons_a": ["ulempe 1", "ulempe 2"],\n'
        f'  "pros_b": ["fordel 1", "fordel 2", "fordel 3"],\n'
        f'  "cons_b": ["ulempe 1", "ulempe 2"],\n'
        f'  "comparison": [\n'
        f'    {{"area": "Dekningsomfang", "doc_a": "hva A sier", "doc_b": "hva B sier", "winner": "A|B|Lik"}}\n'
        f"  ],\n"
        f'  "conclusion": "Samlet konklusjon for forsikringstaker — 3-4 setninger"\n'
        f"}}\n\n"
        f"Inkluder i comparison: Dekningsomfang, Selvrisiko, Forsikringssum, Unntak/begrensninger, "
        f"Særlige vilkår, Forsikringsperiode. winner=A betyr A er bedre, B=B er bedre, Lik=ingen vesentlig forskjell."
    )


class DocumentAnalysisService:
    """Stateless LLM-backed document analysis — no DB session required."""

    def get_document_keypoints(self, doc: InsuranceDocument) -> dict:
        """Extract key points from an InsuranceDocument via text LLM or Gemini PDF fallback."""
        text = doc.extracted_text or ""
        if len(text) > 500:
            raw = _llm_answer_raw(
                f"{_KEYPOINTS_PROMPT}\n\nDokument:\n{text[:LLM_DOCUMENT_CHAR_LIMIT]}"
            )
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
            "sammendrag": (text[:400] + "…")
            if text
            else "Ingen tekstinnhold tilgjengelig",
            "viktige_vilkaar": [],
            "unntak": [],
        }

    def answer_document_question(self, doc: InsuranceDocument, question: str) -> str:
        """Answer a question about an InsuranceDocument. Raises LlmUnavailableError if no LLM."""
        from api.services.llm import _sanitize_user_input

        safe_question = _sanitize_user_input(question)
        prompt = (
            f"Du er en norsk forsikringsrådgiver. Svar alltid på norsk. "
            f"Svar kun basert på innholdet i dette forsikringsdokumentet. "
            f"Vær presis og konkret. Oppgi sidetall eller avsnitt hvis relevant.\n\n"
            f"Spørsmål: {safe_question}"
        )
        answer = _analyze_document_with_gemini(doc.pdf_content, prompt)
        if answer:
            return answer

        if doc.extracted_text is not None:
            fallback = (
                f"Du er en norsk forsikringsrådgiver. Svar alltid på norsk. "
                f"Svar kun basert på dette forsikringsdokumentets innhold:\n\n"
                f"{doc.extracted_text[:LLM_DOCUMENT_CHAR_LIMIT]}\n\nSpørsmål: {question}"
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
                f"{prompt}\n\n--- DOKUMENT A: {a.title} ---\n{text_a[:LLM_DOCUMENT_CHAR_LIMIT]}\n\n--- DOKUMENT B: {b.title} ---\n{text_b[:LLM_DOCUMENT_CHAR_LIMIT]}"
            )
            if raw:
                return _parse_json_from_llm_response(raw) or {"raw_text": raw}

        raw = _compare_documents_with_gemini(a.pdf_content, b.pdf_content, prompt)
        if raw:
            return _parse_json_from_llm_response(raw) or {"raw_text": raw}

        if text_a or text_b:
            raw = _llm_answer_raw(
                f"{prompt}\n\n--- DOKUMENT A: {a.title} ---\n{text_a[:LLM_TEXT_CHAR_LIMIT]}\n\n--- DOKUMENT B: {b.title} ---\n{text_b[:LLM_TEXT_CHAR_LIMIT]}"
            )
            if raw:
                return _parse_json_from_llm_response(raw) or {"raw_text": raw}

        # All three fallback paths returned empty. Most common cause: Gemini
        # timeout on two large PDFs. The user should see a clear "try again"
        # message rather than "no LLM configured".
        raise LlmUnavailableError(
            "AI-sammenligningen kunne ikke fullføres akkurat nå. "
            "Dette skjer oftest når begge PDFene er store og modellen er treg. "
            "Prøv igjen om et øyeblikk, eller last opp mindre utdrag."
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
        tags: Optional[str] = None,
    ) -> InsuranceDocument:
        """Create and persist an InsuranceDocument. Returns the saved ORM row."""
        if not _validate_pdf(pdf_bytes):
            raise ValueError("Ugyldig PDF-fil")
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
            uploaded_at=datetime.now(timezone.utc).isoformat(),
            tags=tags or None,
        )
        self.db.add(doc)
        try:
            self.db.commit()
            self.db.refresh(doc)
        except Exception:
            self.db.rollback()
            raise
        return doc

    def remove_document(self, doc_id: int) -> bool:
        """Delete an InsuranceDocument by ID. Returns True if found and deleted."""
        doc = (
            self.db.query(InsuranceDocument)
            .filter(InsuranceDocument.id == doc_id)
            .first()
        )
        if not doc:
            return False
        self.db.delete(doc)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return True

    def find_similar(self, doc: InsuranceDocument, limit: int = 3) -> list:
        """Return up to `limit` documents most similar to doc by embedding cosine distance."""
        text = (doc.extracted_text or "")[:TEXT_EMBED_CHAR_LIMIT]
        if not text:
            return []
        embedding = _embed(text)
        if not embedding:
            return []
        others = (
            self.db.query(InsuranceDocument)
            .filter(
                InsuranceDocument.id != doc.id,
                InsuranceDocument.extracted_text.isnot(None),
            )
            .all()
        )
        scored = []
        for other in others:
            other_emb = _embed((other.extracted_text or "")[:TEXT_EMBED_CHAR_LIMIT])
            if other_emb:
                sim = _cosine_similarity(embedding, other_emb)
                scored.append(
                    {"id": other.id, "title": other.title, "similarity": round(sim, 4)}
                )
        return sorted(scored, key=lambda x: x["similarity"], reverse=True)[:limit]

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
                item["filename"]
                .rsplit(".", 1)[0]
                .replace("_", " ")
                .replace("-", " ")
                .title()
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
            saved.append(
                {
                    "id": row.id,
                    "filename": row.filename,
                    "insurer_name": row.insurer_name,
                }
            )
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return saved

    def remove_offer(self, offer_id: int, orgnr: str) -> bool:
        """Delete an InsuranceOffer by ID + orgnr. Returns True if found and deleted."""
        row = (
            self.db.query(InsuranceOffer)
            .filter(InsuranceOffer.id == offer_id, InsuranceOffer.orgnr == orgnr)
            .first()
        )
        if not row:
            return False
        self.db.delete(row)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return True


# ── Module-level backward-compat wrappers ─────────────────────────────────────


def store_insurance_document(
    pdf_bytes: bytes,
    filename: str,
    title: str,
    category: str,
    insurer: str,
    year: Optional[int],
    period: str,
    orgnr: Optional[str],
    db: Session,
    tags: Optional[str] = None,
) -> InsuranceDocument:
    return DocumentService(db).store_document(
        pdf_bytes, filename, title, category, insurer, year, period, orgnr, tags
    )


def remove_insurance_document(doc_id: int, db: Session) -> bool:
    return DocumentService(db).remove_document(doc_id)


def get_document_keypoints(doc: InsuranceDocument) -> dict:
    return DocumentAnalysisService().get_document_keypoints(doc)


def answer_document_question(doc: InsuranceDocument, question: str) -> str:
    return DocumentAnalysisService().answer_document_question(doc, question)


def compare_two_documents(a: InsuranceDocument, b: InsuranceDocument) -> dict:
    return DocumentAnalysisService().compare_two_documents(a, b)


def save_insurance_offers(
    orgnr: str, offer_data: List[dict], db: Session
) -> List[dict]:
    return DocumentService(db).save_offers(orgnr, offer_data)


def remove_insurance_offer(offer_id: int, orgnr: str, db: Session) -> bool:
    return DocumentService(db).remove_offer(offer_id, orgnr)


def find_similar_documents(doc: InsuranceDocument, db: Session, limit: int = 3) -> list:
    return DocumentService(db).find_similar(doc, limit)


def _auto_extract_keypoints(doc: InsuranceDocument, db: Session) -> None:
    """Extract keypoints + structured premium data from a document."""
    import logging

    _log = logging.getLogger(__name__)
    if doc.cached_keypoints:
        return
    try:
        kp = DocumentAnalysisService().get_document_keypoints(doc)
        doc.cached_keypoints = kp
        if isinstance(kp, dict):
            _try_parse_premium(doc, kp)
        db.commit()
        _log.info("Doc intel agent: keypoints extracted for doc %d", doc.id)
    except Exception as exc:
        _log.warning(
            "Doc intel agent: keypoint extraction failed for doc %d: %s", doc.id, exc
        )
        db.rollback()


def _auto_compare_tilbuds(doc: InsuranceDocument, db: Session) -> None:
    """If 2+ tilbuds exist for the same orgnr, auto-compare the two most recent."""
    import logging

    _log = logging.getLogger(__name__)
    if not doc.orgnr or doc.category not in (
        "tilbud",
        "forsikringstilbud",
        "tilbud_sammenligning",
    ):
        return
    try:
        others = (
            db.query(InsuranceDocument)
            .filter(
                InsuranceDocument.orgnr == doc.orgnr,
                InsuranceDocument.id != doc.id,
                InsuranceDocument.category.in_(
                    ["tilbud", "forsikringstilbud", "tilbud_sammenligning"]
                ),
            )
            .order_by(InsuranceDocument.id.desc())
            .limit(1)
            .all()
        )
        if others:
            comparison = DocumentAnalysisService().compare_two_documents(doc, others[0])
            doc.auto_comparison_result = comparison
            db.commit()
            _log.info(
                "Doc intel agent: auto-compared doc %d with doc %d",
                doc.id,
                others[0].id,
            )
    except Exception as exc:
        _log.warning(
            "Doc intel agent: auto-comparison failed for doc %d: %s", doc.id, exc
        )
        db.rollback()


def auto_analyze_document(doc_id: int, db: Session) -> None:
    """Background agent: auto-extract keypoints + structured tilbud data.

    Called asynchronously after document upload. Caches results on the
    InsuranceDocument row so subsequent reads don't re-invoke the LLM.
    """
    doc = db.query(InsuranceDocument).filter(InsuranceDocument.id == doc_id).first()
    if not doc:
        return
    _auto_extract_keypoints(doc, db)
    _auto_compare_tilbuds(doc, db)


def _try_parse_premium(doc: InsuranceDocument, kp: dict) -> None:
    """Best-effort extraction of premium/coverage/deductible from keypoints dict."""
    import re

    def _parse_nok(val: str | None) -> float | None:
        if not val:
            return None
        cleaned = re.sub(r"[^\d.,]", "", str(val).replace(" ", ""))
        try:
            return float(cleaned.replace(",", "."))
        except (ValueError, TypeError):
            return None

    if not doc.parsed_premium_nok:
        doc.parsed_premium_nok = _parse_nok(
            kp.get("forsikringspremie") or kp.get("premie")
        )
    if not doc.parsed_coverage_nok:
        doc.parsed_coverage_nok = _parse_nok(kp.get("forsikringssum"))
    if not doc.parsed_deductible_nok:
        doc.parsed_deductible_nok = _parse_nok(kp.get("egenandel"))


def update_offer_status(offer_id: int, orgnr: str, status: str, db: Session) -> bool:
    """Update the win/loss status of a stored offer. Returns False if not found."""
    from api.db import OfferStatus

    row = (
        db.query(InsuranceOffer)
        .filter(InsuranceOffer.id == offer_id, InsuranceOffer.orgnr == orgnr)
        .first()
    )
    if not row:
        return False
    try:
        row.status = OfferStatus(status)
    except ValueError:
        return False
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return True


def parse_and_store_offer(offer_id: int, db_factory=None) -> None:
    """Background task: LLM-extract structured fields from a stored offer and persist them."""
    from api.db import SessionLocal
    from api.services.pdf_generate import _extract_offer_summary

    if db_factory is None:
        db_factory = SessionLocal
    db = db_factory()
    try:
        row = db.query(InsuranceOffer).filter(InsuranceOffer.id == offer_id).first()
        if not row or not row.extracted_text:
            return
        parsed = _extract_offer_summary(
            row.insurer_name or row.filename, row.extracted_text
        )
        row.parsed_premie = parsed.get("premie")
        row.parsed_dekning = parsed.get("dekning")
        row.parsed_egenandel = parsed.get("egenandel")
        row.parsed_vilkaar = parsed.get("vilkaar")
        row.parsed_styrker = parsed.get("styrker")
        row.parsed_svakheter = parsed.get("svakheter")
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
