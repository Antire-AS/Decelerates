"""Demo document generator — creates realistic but fictional insurance documents.

Reads existing InsuranceDocuments from the DB, extracts text via pdfplumber,
adjusts key numbers by ±5–15%, replaces company names with fictional ones,
and saves the result as a new InsuranceDocument tagged 'demo'.
"""

import io
import logging
import random
import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from api.db import InsuranceDocument

_log = logging.getLogger(__name__)

# Fictional Norwegian company names for demo docs
_DEMO_NAMES = [
    "Norsk Industri Holding AS",
    "Bergen Teknologi AS",
    "Trondheim Logistikk AS",
    "Stavanger Eiendom AS",
    "Oslo Handel og Service AS",
    "Vestland Transport AS",
    "Innlandet Produksjon AS",
    "Agder Maritime AS",
]

# Fictional org numbers (valid format but not real)
_DEMO_ORGNRS = [
    "112233445",
    "223344556",
    "334455667",
    "445566778",
    "556677889",
    "667788990",
    "778899001",
    "889900112",
]


def _adjust_number(match: re.Match) -> str:
    """Shift a numeric string by ±5–15% while keeping format."""
    raw = match.group(0)
    # Strip formatting characters and parse
    cleaned = (
        raw.replace("\xa0", "").replace(" ", "").replace(",", ".").replace(".", "")
    )
    try:
        value = int(cleaned)
    except ValueError:
        return raw
    if value == 0:
        return raw
    factor = 1 + random.uniform(-0.15, 0.15)
    new_value = int(value * factor)
    # Preserve original digit-group separators by matching length roughly
    if " " in raw or "\xa0" in raw:
        return f"{new_value:,}".replace(",", "\xa0")
    return str(new_value)


def _anonymise_text(
    text: str, original_name: str, demo_name: str, demo_orgnr: str
) -> str:
    """Replace company name, orgnr, and nudge financial numbers."""
    # Replace company name (case-insensitive)
    if original_name:
        text = re.sub(re.escape(original_name), demo_name, text, flags=re.IGNORECASE)
    # Replace 9-digit org numbers
    text = re.sub(r"\b\d{3}\s?\d{3}\s?\d{3}\b", demo_orgnr, text)
    # Nudge standalone NOK amounts (4-9 digit numbers, possibly space-separated)
    text = re.sub(r"\b\d[\d\s]{3,10}\d\b", _adjust_number, text)
    return text


def _text_to_pdf(text: str, title: str) -> bytes:
    """Convert plain text to a simple PDF using fpdf2."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(0, 8, title)
    pdf.ln(4)
    pdf.set_font("Helvetica", size=9)
    for line in text.splitlines():
        try:
            pdf.multi_cell(0, 5, line[:200])
        except Exception:
            pass
    return pdf.output()


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract all text from PDF bytes using pdfplumber."""
    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages[:30])
    except Exception as exc:
        _log.warning("pdfplumber extraction failed: %s", exc)
        return ""


class DemoDocumentsService:
    def __init__(self, db: Session):
        self.db = db

    def seed_demo_documents(self, max_source_docs: int = 5) -> dict:
        """Read real InsuranceDocuments, anonymise them, save as demo copies.

        Skips documents already tagged 'demo'. Returns counts.
        """
        existing_demo = {
            d.title
            for d in self.db.query(InsuranceDocument.title)
            .filter(InsuranceDocument.tags.like("%demo%"))
            .all()
        }

        sources = (
            self.db.query(InsuranceDocument)
            .filter(~InsuranceDocument.tags.like("%demo%"))
            .limit(max_source_docs)
            .all()
        )

        if not sources:
            return {
                "created": 0,
                "skipped": 0,
                "reason": "No source documents found in DB",
            }

        created, skipped = 0, 0
        for i, src in enumerate(sources):
            demo_title = f"[Demo] {src.title}"
            if demo_title in existing_demo:
                skipped += 1
                continue

            demo_name = _DEMO_NAMES[i % len(_DEMO_NAMES)]
            demo_orgnr = _DEMO_ORGNRS[i % len(_DEMO_ORGNRS)]

            text = _extract_pdf_text(src.pdf_content)
            if not text.strip():
                skipped += 1
                _log.warning("demo_docs: no text extracted from doc id=%s", src.id)
                continue

            anonymised = _anonymise_text(text, src.orgnr or "", demo_name, demo_orgnr)
            try:
                pdf_bytes = _text_to_pdf(anonymised, demo_title)
            except Exception as exc:
                _log.warning(
                    "demo_docs: PDF generation failed for %s: %s", src.title, exc
                )
                skipped += 1
                continue

            now = datetime.now(timezone.utc).isoformat()
            self.db.add(
                InsuranceDocument(
                    title=demo_title,
                    category=src.category,
                    insurer=src.insurer,
                    year=src.year,
                    period=src.period,
                    orgnr=demo_orgnr,
                    filename=f"demo_{src.filename}",
                    pdf_content=pdf_bytes,
                    extracted_text=anonymised,
                    uploaded_at=now,
                    tags="demo",
                )
            )
            created += 1

        self.db.commit()
        return {"created": created, "skipped": skipped}


# Backward compat
def seed_demo_documents(db: Session, max_source_docs: int = 5) -> dict:
    return DemoDocumentsService(db).seed_demo_documents(max_source_docs)
