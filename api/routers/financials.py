from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session

from api.db import CompanyHistory, CompanyPdfSource
from api.limiter import limiter
from api.services import _get_full_history, fetch_history_from_pdf
from api.services.pdf_sources import upsert_pdf_source, delete_history_year
from api.schemas import PdfHistoryRequest
from api.domain.exceptions import PdfExtractionError
from api.dependencies import get_db

router = APIRouter()


@router.get("/org/{orgnr}/history")
def get_org_history(orgnr: str, db: Session = Depends(get_db)) -> dict:
    history = _get_full_history(orgnr, db)
    return {"orgnr": orgnr, "years": history}


@router.post("/org/{orgnr}/pdf-history")
def add_pdf_history(orgnr: str, body: PdfHistoryRequest, db: Session = Depends(get_db)) -> dict:
    """Add a PDF annual report URL for an org, extract financials, store in DB."""
    upsert_pdf_source(orgnr, body.year, body.pdf_url, body.label, db)
    try:
        row = fetch_history_from_pdf(orgnr, body.pdf_url, body.year, body.label, db)
    except PdfExtractionError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"PDF extraction failed: {e}")
    return {"orgnr": orgnr, "extracted": row}


@router.get("/org/{orgnr}/pdf-sources")
def get_pdf_sources(orgnr: str, db: Session = Depends(get_db)) -> dict:
    """List known PDF annual report sources for an org."""
    sources = (
        db.query(CompanyPdfSource)
        .filter(CompanyPdfSource.orgnr == orgnr)
        .order_by(CompanyPdfSource.year.desc())
        .all()
    )
    return {
        "orgnr": orgnr,
        "sources": [
            {"year": s.year, "pdf_url": s.pdf_url, "label": s.label, "added_at": s.added_at}
            for s in sources
        ],
    }


@router.get("/org/{orgnr}/extraction-status")
def get_extraction_status(orgnr: str, db: Session = Depends(get_db)) -> dict:
    """Return whether background PDF extraction has data, is pending, or is complete."""
    sources = db.query(CompanyPdfSource).filter(CompanyPdfSource.orgnr == orgnr).all()
    extracted_years = {
        r.year for r in db.query(CompanyHistory).filter(CompanyHistory.orgnr == orgnr).all()
    }
    source_years = {s.year for s in sources}
    pending_years = sorted(source_years - extracted_years)
    done_years = sorted(source_years & extracted_years)
    current_year = datetime.now().year
    target = set(range(current_year - 5, current_year))
    if not sources:
        status = "no_sources"
    elif pending_years:
        status = "extracting"
    elif not extracted_years:
        status = "no_data"
    else:
        status = "done"
    return {
        "orgnr": orgnr,
        "status": status,
        "source_years": sorted(source_years),
        "done_years": done_years,
        "pending_years": pending_years,
        "missing_target_years": sorted(target - source_years),
    }


@router.delete("/org/{orgnr}/history")
def reset_history(orgnr: str, db: Session = Depends(get_db)) -> dict:
    """Delete all company_history rows for this org so extraction re-runs on next load."""
    deleted = delete_history_year(orgnr, db)
    return {"orgnr": orgnr, "deleted_rows": deleted}


@router.get("/org/{orgnr}/financial-commentary")
@limiter.limit("10/minute")
def get_financial_commentary(request: Request, orgnr: str, db: Session = Depends(get_db)) -> dict:
    """Generate an AI commentary on a company's multi-year financial trend."""
    from api.services.llm import _llm_answer_raw
    from api.db import Company

    company = db.query(Company).filter(Company.orgnr == orgnr).first()
    history = _get_full_history(orgnr, db)
    if not history:
        raise HTTPException(status_code=404, detail="No financial history found for this company")

    navn = company.navn if company else orgnr
    years_summary = "\n".join(
        f"- {h['year']}: omsetning {h.get('sum_driftsinntekter') or 'N/A'} NOK, "
        f"egenkapital {h.get('sum_egenkapital') or 'N/A'} NOK, "
        f"eiendeler {h.get('sum_eiendeler') or 'N/A'} NOK"
        for h in sorted(history, key=lambda x: x.get("year", 0))
    )
    prompt = (
        f"Du er en norsk finansanalytiker. Gi en kortfattet kommentar (3–5 setninger, norsk) "
        f"om det finansielle trendbildet for {navn} (orgnr {orgnr}) basert på disse tallene:\n\n"
        f"{years_summary}\n\n"
        "Fokuser på utvikling i omsetning, egenkapital og balanse. "
        "Vær objektiv og profesjonell. Avslutt med ett konkret risikonivå: Lav / Moderat / Høy."
    )
    commentary = _llm_answer_raw(prompt)
    if not commentary:
        raise HTTPException(status_code=503, detail="LLM not available — check ANTHROPIC_API_KEY or GEMINI_API_KEY")
    return {"orgnr": orgnr, "navn": navn, "commentary": commentary, "years_analyzed": len(history)}


@router.post("/financials/query")
@limiter.limit("20/minute")
def nl_query(request: Request, body: dict, db: Session = Depends(get_db)) -> dict:
    """Convert a natural-language question to SQL and return results.

    Body: {"question": "Which 10 companies have the highest revenue?"}
    Returns: {"sql": "...", "columns": [...], "rows": [...], "error": null}
    """
    question = (body.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    from api.services.nl_query import run_nl_query
    return run_nl_query(question, db)
