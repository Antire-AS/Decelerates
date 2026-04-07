import io
import os
import re
from typing import Any, List

from fastapi import APIRouter, HTTPException, Depends, File, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import pdfplumber

_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
_ALLOWED_MIME_TYPES = {"application/pdf"}
_MAX_FILES = 20


def _safe_filename(name: str) -> str:
    name = os.path.basename(name)
    name = re.sub(r"[^\w.\-]", "_", name)
    return name or "offer.pdf"

from api.db import Company, InsuranceOffer
from api.limiter import limiter
from api.services.llm import _compare_offers_with_llm
from api.services.documents import (
    save_insurance_offers, remove_insurance_offer,
    update_offer_status, _pdf_bytes_to_text,
)
from api.dependencies import get_db
from api.services.audit import log_audit
from api.services.job_queue_service import JobQueueService, register_handler

router = APIRouter()


def _company_context_str(company: Any, orgnr: str) -> str:
    if not company:
        return orgnr
    parts = [company.navn or orgnr]
    if company.naeringskode1_beskrivelse:
        parts.append(company.naeringskode1_beskrivelse)
    if company.risk_score is not None:
        parts.append(f"risikoscore {company.risk_score}")
    return ", ".join(parts)


def _compare_prompt(n_offers: int, company_ctx: str, offers_block: str) -> str:
    return f"""Du er en erfaren forsikringsmegler som analyserer {n_offers} forsikringstilbud for en norsk bedrift.

Bedrift: {company_ctx}

{offers_block}

Svar på norsk med disse seksjonene:

## Sammendrag
For hvert tilbud: 2-3 setninger om dekningsomfang, pris og særlige vilkår.

## Sammenligningstabell
Markdown-tabell med kolonnene: Selskap | Dekningstype | Premie/pris | Egenandel | Særlige vilkår | Styrker | Svakheter

## Anbefaling
Hvilket tilbud passer best for denne bedriften og hvorfor.

## Forhandlingspunkter
3-5 konkrete punkter megler bør ta opp med forsikringsselskapet."""


@router.post("/org/{orgnr}/offers/compare")
@limiter.limit("20/minute")
async def compare_offers(
    request: Request,
    orgnr: str,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Extract text from uploaded offer PDFs and return an AI comparison."""
    if len(files) > _MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Maximum {_MAX_FILES} files per request")
    company = db.query(Company).filter(Company.orgnr == orgnr).first()
    company_ctx = _company_context_str(company, orgnr)

    offer_texts = []
    for f in files:
        if f.content_type not in _ALLOWED_MIME_TYPES:
            raise HTTPException(status_code=415, detail=f"{f.filename}: only PDF files are accepted")
        raw = await f.read()
        if len(raw) > _MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"{f.filename}: file exceeds 50 MB limit")
        try:
            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                text = "\n".join(p.extract_text() or "" for p in pdf.pages[:40])
        except Exception:
            text = "(kunne ikke lese PDF)"
        offer_texts.append({"name": f.filename or f"Tilbud {len(offer_texts)+1}", "text": text[:10000]})

    offers_block = "\n\n".join(
        f"=== TILBUD {i+1}: {o['name']} ===\n{o['text']}"
        for i, o in enumerate(offer_texts)
    )
    comparison = _compare_offers_with_llm(_compare_prompt(len(offer_texts), company_ctx, offers_block))
    return {"orgnr": orgnr, "offers": [o["name"] for o in offer_texts], "comparison": comparison}


def _handle_offer_parse(db, payload: dict):
    from api.services.documents import parse_and_store_offer
    parse_and_store_offer(payload.get("offer_id"))


register_handler("offer_parse", _handle_offer_parse)


@router.post("/org/{orgnr}/offers")
@limiter.limit("30/minute")
async def save_offers(
    request: Request,
    orgnr: str,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Upload and persist offer PDFs; schedules background LLM parsing of structured fields."""
    if len(files) > _MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Maximum {_MAX_FILES} files per request")
    offer_data = []
    for f in files:
        if f.content_type not in _ALLOWED_MIME_TYPES:
            raise HTTPException(status_code=415, detail=f"{f.filename}: only PDF files are accepted")
        raw = await f.read()
        if len(raw) > _MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"{f.filename}: file exceeds 50 MB limit")
        offer_data.append({
            "filename": _safe_filename(f.filename or "offer.pdf"),
            "raw_bytes": raw,
            "extracted_text": _pdf_bytes_to_text(raw) or None,
        })
    saved = save_insurance_offers(orgnr, offer_data, db)
    jq = JobQueueService(db)
    for item in saved:
        if item.get("id"):
            jq.enqueue("offer_parse", {"offer_id": item["id"]})
    log_audit(db, "offer.upload", orgnr=orgnr, detail={"count": len(saved)})
    return {"orgnr": orgnr, "saved": saved}


@router.get("/org/{orgnr}/offers")
def list_offers(orgnr: str, db: Session = Depends(get_db)) -> list:
    """List stored offer PDFs for a company."""
    rows = db.query(InsuranceOffer).filter(InsuranceOffer.orgnr == orgnr).order_by(InsuranceOffer.id).all()
    return [
        {
            "id": r.id,
            "filename": r.filename,
            "insurer_name": r.insurer_name,
            "uploaded_at": r.uploaded_at,
            "has_text": bool(r.extracted_text),
            "parsed": bool(r.parsed_premie),
            "premie": r.parsed_premie,
            "dekning": r.parsed_dekning,
            "egenandel": r.parsed_egenandel,
            "vilkaar": r.parsed_vilkaar,
            "styrker": r.parsed_styrker,
            "svakheter": r.parsed_svakheter,
            "status": r.status.value if r.status else "pending",
        }
        for r in rows
    ]


@router.patch("/org/{orgnr}/offers/{offer_id}/status")
def set_offer_status(
    orgnr: str,
    offer_id: int,
    body: dict,
    db: Session = Depends(get_db),
) -> dict:
    """Update the win/loss status of an offer (pending/accepted/rejected/negotiating)."""
    status = (body.get("status") or "").strip()
    if not status:
        raise HTTPException(status_code=400, detail="status is required")
    if not update_offer_status(offer_id, orgnr, status, db):
        raise HTTPException(status_code=404, detail="Offer not found or invalid status")
    log_audit(db, "offer.status_change", orgnr=orgnr,
              detail={"offer_id": offer_id, "status": status})
    return {"id": offer_id, "status": status}


@router.delete("/org/{orgnr}/offers/{offer_id}")
def delete_offer(orgnr: str, offer_id: int, db: Session = Depends(get_db)) -> dict:
    if not remove_insurance_offer(offer_id, orgnr, db):
        raise HTTPException(status_code=404, detail="Offer not found")
    log_audit(db, "offer.delete", orgnr=orgnr, detail={"offer_id": offer_id})
    return {"deleted": offer_id}


@router.get("/org/{orgnr}/offers/{offer_id}/pdf")
def download_offer_pdf(orgnr: str, offer_id: int, db: Session = Depends(get_db)):
    row = db.query(InsuranceOffer).filter(
        InsuranceOffer.id == offer_id, InsuranceOffer.orgnr == orgnr
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Offer not found")
    return StreamingResponse(
        io.BytesIO(row.pdf_content),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{row.filename}"'},
    )


@router.post("/org/{orgnr}/offers/compare-stored")
def compare_stored_offers(
    orgnr: str,
    offer_ids: List[int],
    db: Session = Depends(get_db),
):
    """Run AI comparison on already-stored offer PDFs."""
    rows = db.query(InsuranceOffer).filter(
        InsuranceOffer.orgnr == orgnr,
        InsuranceOffer.id.in_(offer_ids),
    ).all()
    if not rows:
        raise HTTPException(status_code=404, detail="No offers found")

    company = db.query(Company).filter(Company.orgnr == orgnr).first()
    company_ctx = _company_context_str(company, orgnr)
    offers_block = "\n\n".join(
        f"=== TILBUD {i+1}: {r.insurer_name} ({r.filename}) ===\n{(r.extracted_text or '')[:10000]}"
        for i, r in enumerate(rows)
    )
    comparison = _compare_offers_with_llm(_compare_prompt(len(rows), company_ctx, offers_block))
    return {"orgnr": orgnr, "offers": [r.insurer_name for r in rows], "comparison": comparison}
