import io
import json
from typing import List

from fastapi import APIRouter, HTTPException, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import pdfplumber

from db import Company, InsuranceOffer
from services import _llm_answer_raw
from services.llm import _compare_offers_with_llm
from services.documents import save_insurance_offers, remove_insurance_offer, _pdf_bytes_to_text
from dependencies import get_db

router = APIRouter()


@router.post("/org/{orgnr}/offers/compare")
async def compare_offers(
    orgnr: str,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Extract text from uploaded offer PDFs and return an AI comparison."""
    company = db.query(Company).filter(Company.orgnr == orgnr).first()
    company_ctx = ""
    if company:
        parts = [company.navn or orgnr]
        if company.naeringskode1_beskrivelse:
            parts.append(company.naeringskode1_beskrivelse)
        if company.risk_score is not None:
            parts.append(f"risikoscore {company.risk_score}")
        company_ctx = ", ".join(parts)
    else:
        company_ctx = orgnr

    offer_texts = []
    for f in files:
        raw = await f.read()
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

    prompt = f"""Du er en erfaren forsikringsmegler som analyserer {len(offer_texts)} forsikringstilbud for en norsk bedrift.

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

    comparison = _compare_offers_with_llm(prompt)
    return {
        "orgnr": orgnr,
        "offers": [o["name"] for o in offer_texts],
        "comparison": comparison,
    }


@router.post("/org/{orgnr}/offers")
async def save_offers(
    orgnr: str,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Upload and persist offer PDFs for a company."""
    offer_data = []
    for f in files:
        raw = await f.read()
        offer_data.append({
            "filename": f.filename or "offer.pdf",
            "raw_bytes": raw,
            "extracted_text": _pdf_bytes_to_text(raw) or None,
        })
    saved = save_insurance_offers(orgnr, offer_data, db)
    return {"orgnr": orgnr, "saved": saved}


@router.get("/org/{orgnr}/offers")
def list_offers(orgnr: str, db: Session = Depends(get_db)):
    """List stored offer PDFs for a company."""
    rows = db.query(InsuranceOffer).filter(InsuranceOffer.orgnr == orgnr).order_by(InsuranceOffer.id).all()
    return [
        {
            "id": r.id,
            "filename": r.filename,
            "insurer_name": r.insurer_name,
            "uploaded_at": r.uploaded_at,
            "has_text": bool(r.extracted_text),
        }
        for r in rows
    ]


@router.delete("/org/{orgnr}/offers/{offer_id}")
def delete_offer(orgnr: str, offer_id: int, db: Session = Depends(get_db)):
    if not remove_insurance_offer(offer_id, orgnr, db):
        raise HTTPException(status_code=404, detail="Offer not found")
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
    company_ctx = company.navn if company else orgnr

    offers_block = "\n\n".join(
        f"=== TILBUD {i+1}: {r.insurer_name} ({r.filename}) ===\n{(r.extracted_text or '')[:10000]}"
        for i, r in enumerate(rows)
    )

    prompt = f"""Du er en erfaren forsikringsmegler som analyserer {len(rows)} forsikringstilbud for en norsk bedrift.

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

    comparison = _compare_offers_with_llm(prompt)
    return {
        "orgnr": orgnr,
        "offers": [r.insurer_name for r in rows],
        "comparison": comparison,
    }
