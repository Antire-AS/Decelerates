from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from db import CompanyPdfSource
from services import _get_full_history, fetch_history_from_pdf
from services.pdf_sources import upsert_pdf_source, delete_history_year
from schemas import PdfHistoryRequest
from domain.exceptions import PdfExtractionError
from dependencies import get_db

router = APIRouter()


@router.get("/org/{orgnr}/history")
def get_org_history(orgnr: str, db: Session = Depends(get_db)):
    history = _get_full_history(orgnr, db)
    return {"orgnr": orgnr, "years": history}


@router.post("/org/{orgnr}/pdf-history")
def add_pdf_history(orgnr: str, body: PdfHistoryRequest, db: Session = Depends(get_db)):
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
def get_pdf_sources(orgnr: str, db: Session = Depends(get_db)):
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


@router.delete("/org/{orgnr}/history")
def reset_history(orgnr: str, db: Session = Depends(get_db)):
    """Delete all company_history rows for this org so extraction re-runs on next load."""
    deleted = delete_history_year(orgnr, db)
    return {"orgnr": orgnr, "deleted_rows": deleted}
