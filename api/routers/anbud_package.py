"""Anbudspakke-PDF download endpoint."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from api.dependencies import get_db
from api.domain.exceptions import NotFoundError
from api.services.pdf_anbud import build_anbudspakke_data, generate_anbudspakke_pdf

router = APIRouter()


@router.get("/org/{orgnr}/anbudspakke.pdf")
def download_anbudspakke(orgnr: str, db: Session = Depends(get_db)) -> Response:
    """Return a PDF bundling all underwriting-relevant data about the
    company — one document the broker attaches when soliciting offers
    from insurers. No auth wall beyond what /org/{orgnr} already has."""
    try:
        data = build_anbudspakke_data(orgnr, db)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    pdf_bytes = generate_anbudspakke_pdf(data)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="anbudspakke-{orgnr}.pdf"',
        },
    )
