"""Coverage analysis service — AI-powered policy document interpretation.

Replaces the 4-5 hours a broker spends manually reading vilkårstekster.
Extracts structured coverage details: what's covered, deductibles, limits,
exclusions, waiting periods.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

import pdfplumber
from sqlalchemy.orm import Session

from api.db import CoverageAnalysis

logger = logging.getLogger(__name__)

# Structured extraction prompt — returns JSON with coverage breakdown
_COVERAGE_PROMPT = """Du er en ekspert på norske forsikringsvilkår. Analyser dette forsikringsdokumentet og returner en JSON-struktur med følgende felter:

{
  "forsikringstype": "type forsikring (f.eks. Ansvarsforsikring, Eiendomsforsikring, Personalforsikring)",
  "forsikringsgiver": "navn på forsikringsselskapet",
  "polisenummer": "polisenummer hvis oppgitt",
  "gyldig_fra": "startdato",
  "gyldig_til": "sluttdato",
  "premie_nok": 0,
  "egenandel_nok": 0,
  "forsikringssum_nok": 0,
  "dekninger": [
    {
      "navn": "navn på dekningen",
      "beskrivelse": "hva som er dekket",
      "sum_nok": 0,
      "egenandel_nok": 0,
      "karenstid": "eventuell karenstid",
      "begrensninger": "eventuelle begrensninger"
    }
  ],
  "unntak": ["liste over hva som IKKE er dekket"],
  "særvilkår": ["spesielle vilkår eller klausuler"],
  "oppsummering": "kort oppsummering av dekningens omfang og kvalitet på 2-3 setninger"
}

Vær nøyaktig med tall. Hvis et felt ikke finnes i dokumentet, bruk null.
Returner KUN gyldig JSON, ingen annen tekst."""


class CoverageService:
    """Analyses insurance policy documents to extract structured coverage info."""

    def __init__(self, db: Session):
        self.db = db

    def create_analysis(
        self,
        orgnr: str,
        firm_id: int,
        title: str,
        pdf_bytes: bytes,
        filename: str,
        insurer: Optional[str] = None,
        product_type: Optional[str] = None,
        document_id: Optional[int] = None,
    ) -> CoverageAnalysis:
        """Store a policy PDF and kick off AI analysis."""
        # Extract text via pdfplumber for search/fallback
        extracted_text = _extract_text(pdf_bytes)

        analysis = CoverageAnalysis(
            orgnr=orgnr,
            firm_id=firm_id,
            document_id=document_id,
            title=title,
            insurer=insurer,
            product_type=product_type,
            filename=filename,
            pdf_content=pdf_bytes,
            extracted_text=extracted_text,
            status="pending",
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def run_analysis(self, analysis_id: int) -> CoverageAnalysis:
        """Run AI extraction on a pending coverage analysis."""
        analysis = self.db.query(CoverageAnalysis).get(analysis_id)
        if not analysis:
            raise ValueError(f"Coverage analysis {analysis_id} not found")

        try:
            result = _analyse_with_ai(analysis.pdf_content, analysis.extracted_text)
            if result:
                analysis.coverage_data = result
                analysis.premium_nok = _safe_float(result.get("premie_nok"))
                analysis.deductible_nok = _safe_float(result.get("egenandel_nok"))
                analysis.coverage_sum_nok = _safe_float(result.get("forsikringssum_nok"))
                if not analysis.insurer and result.get("forsikringsgiver"):
                    analysis.insurer = result["forsikringsgiver"]
                if not analysis.product_type and result.get("forsikringstype"):
                    analysis.product_type = result["forsikringstype"]
                analysis.status = "analysed"
            else:
                analysis.status = "error"
        except Exception as exc:
            logger.error("Coverage analysis %d failed: %s", analysis_id, exc)
            analysis.status = "error"

        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def list_for_company(self, orgnr: str) -> list:
        return (
            self.db.query(CoverageAnalysis)
            .filter(CoverageAnalysis.orgnr == orgnr)
            .order_by(CoverageAnalysis.created_at.desc())
            .all()
        )

    def get(self, analysis_id: int) -> Optional[CoverageAnalysis]:
        return self.db.query(CoverageAnalysis).get(analysis_id)

    def delete(self, analysis_id: int) -> bool:
        row = self.db.query(CoverageAnalysis).get(analysis_id)
        if not row:
            return False
        self.db.delete(row)
        self.db.commit()
        return True


def _extract_text(pdf_bytes: bytes) -> Optional[str]:
    """Extract text from PDF using pdfplumber."""
    try:
        import io
        pages = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages[:40]:
                text = page.extract_text()
                if text:
                    pages.append(text)
        return "\n\n".join(pages) if pages else None
    except Exception as exc:
        logger.warning("pdfplumber extraction failed: %s", exc)
        return None


def _analyse_with_ai(pdf_bytes: bytes, extracted_text: Optional[str]) -> Optional[dict]:
    """Try Gemini PDF analysis first, fall back to Foundry text analysis."""
    from api.services.llm import (
        _analyze_document_with_gemini,
        _try_foundry_chat,
        _parse_json_from_llm_response,
    )

    # Try Gemini (native PDF input — best for scanned docs)
    raw = _analyze_document_with_gemini(pdf_bytes, _COVERAGE_PROMPT)
    if raw:
        parsed = _parse_json_from_llm_response(raw)
        if parsed:
            return parsed

    # Fallback: text-based analysis via Foundry
    if extracted_text:
        raw = _try_foundry_chat(
            f"Her er teksten fra et forsikringsdokument:\n\n{extracted_text[:12000]}",
            _COVERAGE_PROMPT,
            max_tokens=4000,
        )
        if raw:
            parsed = _parse_json_from_llm_response(raw)
            if parsed:
                return parsed

    return None


def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
