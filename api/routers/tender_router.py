"""Tender (anbud) endpoints — create, send, collect offers, and compare."""

import logging
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from api.auth import get_current_user
from api.db import User
from api.dependencies import get_db
from api.limiter import limiter
from api.schemas import (
    TenderCreate,
    TenderUpdate,
    TenderOut,
    TenderListOut,
    TenderAnalysisOut,
    TenderOfferOut,
)
from api.services.tender_service import TenderService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["tenders"])

_MAX_PDF_BYTES = 50 * 1024 * 1024


def _svc(db: Session = Depends(get_db)) -> TenderService:
    return TenderService(db)


@router.post("/tenders", response_model=TenderOut)
@limiter.limit("20/minute")
async def create_tender(
    request: Request,
    body: TenderCreate,
    svc: TenderService = Depends(_svc),
    user: User = Depends(get_current_user),
):
    """Create a new tender (anbud)."""
    tender = svc.create(
        orgnr=body.orgnr,
        firm_id=user.firm_id,
        title=body.title,
        product_types=body.product_types,
        deadline=body.deadline,
        notes=body.notes,
        created_by_email=user.email,
        recipients=[r.model_dump() for r in body.recipients],
    )
    return _to_detail(tender, svc)


@router.get("/tenders", response_model=List[TenderListOut])
@limiter.limit("30/minute")
async def list_tenders(
    request: Request,
    orgnr: str = None,
    svc: TenderService = Depends(_svc),
    user: User = Depends(get_current_user),
):
    """List tenders, optionally filtered by company."""
    if orgnr:
        tenders = svc.list_for_company(orgnr, user.firm_id)
    else:
        tenders = svc.list_all(user.firm_id)

    result = []
    for t in tenders:
        recipients = svc.get_recipients(t.id)
        offers = svc.get_offers(t.id)
        result.append(
            {
                "id": t.id,
                "orgnr": t.orgnr,
                "title": t.title,
                "product_types": t.product_types or [],
                "deadline": t.deadline,
                "status": t.status.value if hasattr(t.status, "value") else t.status,
                "recipient_count": len(recipients),
                "offer_count": len(offers),
                "created_at": t.created_at,
            }
        )
    return result


@router.get("/tenders/{tender_id}", response_model=TenderOut)
@limiter.limit("30/minute")
async def get_tender(
    request: Request,
    tender_id: int,
    svc: TenderService = Depends(_svc),
    user: User = Depends(get_current_user),
):
    """Get tender details with recipients and offers."""
    tender = svc.get(tender_id, user.firm_id)
    if not tender:
        raise HTTPException(status_code=404, detail="Anbud ikke funnet")
    return _to_detail(tender, svc)


@router.patch("/tenders/{tender_id}", response_model=TenderOut)
@limiter.limit("20/minute")
async def update_tender(
    request: Request,
    tender_id: int,
    body: TenderUpdate,
    svc: TenderService = Depends(_svc),
    user: User = Depends(get_current_user),
):
    """Update tender fields."""
    updates = body.model_dump(exclude_none=True)
    tender = svc.update(tender_id, user.firm_id, **updates)
    if not tender:
        raise HTTPException(status_code=404, detail="Anbud ikke funnet")
    return _to_detail(tender, svc)


@router.delete("/tenders/{tender_id}")
@limiter.limit("20/minute")
async def delete_tender(
    request: Request,
    tender_id: int,
    svc: TenderService = Depends(_svc),
    user: User = Depends(get_current_user),
):
    """Delete a tender and all associated offers."""
    if not svc.delete(tender_id, user.firm_id):
        raise HTTPException(status_code=404, detail="Anbud ikke funnet")
    return {"deleted": True}


@router.post("/tenders/{tender_id}/send", response_model=TenderOut)
@limiter.limit("5/minute")
async def send_tender(
    request: Request,
    tender_id: int,
    svc: TenderService = Depends(_svc),
    user: User = Depends(get_current_user),
):
    """Send tender invitations to all recipients via email."""
    try:
        tender = svc.send_invitations(tender_id, user.firm_id)
        return _to_detail(tender, svc)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/tenders/{tender_id}/recipients")
@limiter.limit("20/minute")
async def add_recipient(
    request: Request,
    tender_id: int,
    insurer_name: str = Form(...),
    insurer_email: str = Form(""),
    svc: TenderService = Depends(_svc),
    user: User = Depends(get_current_user),
):
    """Add a recipient to a tender."""
    r = svc.add_recipient(tender_id, insurer_name, insurer_email or None)
    return {
        "id": r.id,
        "tender_id": r.tender_id,
        "insurer_name": r.insurer_name,
        "insurer_email": r.insurer_email,
        "status": r.status.value if hasattr(r.status, "value") else r.status,
    }


# ── Insurer portal (token-based, no auth required) ───────────────────────────


@router.get("/tenders/portal/{access_token}")
def portal_get_tender(
    access_token: str, svc: TenderService = Depends(_svc), db: Session = Depends(get_db)
) -> dict:
    """Read-only tender view for the insurer portal.

    Returns what the invited insurer needs to quote: tender title, product list,
    deadline, broker's notes, and the client company name. No broker login
    required — just the unique access token issued when the recipient was added.
    """
    recipient = svc.get_recipient_by_token(access_token)
    if not recipient:
        raise HTTPException(status_code=404, detail="Ugyldig lenke")
    tender = svc.db.query(
        __import__("api.models.tender", fromlist=["Tender"]).Tender
    ).get(recipient.tender_id)
    if not tender:
        raise HTTPException(status_code=404, detail="Anbud ikke funnet")
    from api.db import Company

    company = db.query(Company).filter(Company.orgnr == tender.orgnr).first()
    return {
        "insurer_name": recipient.insurer_name,
        "status": recipient.status.value
        if hasattr(recipient.status, "value")
        else recipient.status,
        "tender": {
            "title": tender.title,
            "orgnr": tender.orgnr,
            "company_name": company.navn if company else tender.orgnr,
            "product_types": tender.product_types,
            "deadline": tender.deadline.isoformat() if tender.deadline else None,
            "notes": tender.notes,
        },
    }


@router.post("/tenders/portal/{access_token}/upload", response_model=TenderOfferOut)
@limiter.limit("5/minute")
async def portal_upload_offer(
    request: Request,
    access_token: str,
    file: UploadFile = File(...),
    svc: TenderService = Depends(_svc),
):
    """Insurer uploads their quote via the portal link. No auth required."""
    if file.content_type and file.content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="Kun PDF-filer er støttet")
    raw = await file.read()
    if len(raw) > _MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="Fil for stor (maks 50 MB)")
    try:
        offer = svc.upload_offer_by_token(
            access_token=access_token,
            filename=file.filename or "tilbud.pdf",
            pdf_content=raw,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="Ugyldig lenke")
    # Best-effort structured extraction; don't fail the upload if it errors.
    try:
        svc.extract_offer(offer.id)
    except Exception as exc:
        logger.warning("Portal offer extraction failed for %d: %s", offer.id, exc)
    return {
        "id": offer.id,
        "tender_id": offer.tender_id,
        "recipient_id": offer.recipient_id,
        "insurer_name": offer.insurer_name,
        "filename": offer.filename,
        "extracted_data": offer.extracted_data,
        "uploaded_at": offer.uploaded_at,
    }


@router.post("/tenders/{tender_id}/offers", response_model=TenderOfferOut)
@limiter.limit("10/minute")
async def upload_offer(
    request: Request,
    tender_id: int,
    file: UploadFile = File(...),
    insurer_name: str = Form(...),
    recipient_id: int = Form(None),
    svc: TenderService = Depends(_svc),
    user: User = Depends(get_current_user),
):
    """Upload a PDF offer from an insurer."""
    if file.content_type and file.content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="Kun PDF-filer er støttet")

    raw = await file.read()
    if len(raw) > _MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="Fil for stor (maks 50 MB)")

    offer = svc.upload_offer(
        tender_id=tender_id,
        insurer_name=insurer_name,
        filename=file.filename or "tilbud.pdf",
        pdf_bytes=raw,
        recipient_id=recipient_id or None,
    )

    # Extract structured data in background
    try:
        svc.extract_offer(offer.id)
    except Exception as exc:
        logger.warning("Offer extraction failed for %d: %s", offer.id, exc)

    return {
        "id": offer.id,
        "tender_id": offer.tender_id,
        "recipient_id": offer.recipient_id,
        "insurer_name": offer.insurer_name,
        "filename": offer.filename,
        "extracted_data": offer.extracted_data,
        "uploaded_at": offer.uploaded_at,
    }


@router.post("/tenders/{tender_id}/analyse", response_model=TenderAnalysisOut)
@limiter.limit("5/minute")
async def analyse_tender(
    request: Request,
    tender_id: int,
    svc: TenderService = Depends(_svc),
    user: User = Depends(get_current_user),
):
    """Run AI comparison of all offers in a tender."""
    try:
        result = svc.analyse_offers(tender_id, user.firm_id)
        return {"tender_id": tender_id, "analysis": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _to_detail(tender, svc: TenderService) -> dict:
    """Build full TenderOut dict."""
    recipients = svc.get_recipients(tender.id)
    offers = svc.get_offers(tender.id)

    return {
        "id": tender.id,
        "orgnr": tender.orgnr,
        "title": tender.title,
        "product_types": tender.product_types or [],
        "deadline": tender.deadline,
        "notes": tender.notes,
        "status": tender.status.value
        if hasattr(tender.status, "value")
        else tender.status,
        "analysis_result": tender.analysis_result,
        "created_by_email": tender.created_by_email,
        "created_at": tender.created_at,
        "recipients": [
            {
                "id": r.id,
                "tender_id": r.tender_id,
                "insurer_name": r.insurer_name,
                "insurer_email": r.insurer_email,
                "status": r.status.value if hasattr(r.status, "value") else r.status,
                "sent_at": r.sent_at,
                "response_at": r.response_at,
            }
            for r in recipients
        ],
        "offers": [
            {
                "id": o.id,
                "tender_id": o.tender_id,
                "recipient_id": o.recipient_id,
                "insurer_name": o.insurer_name,
                "filename": o.filename,
                "extracted_data": o.extracted_data,
                "uploaded_at": o.uploaded_at,
            }
            for o in offers
        ],
    }
