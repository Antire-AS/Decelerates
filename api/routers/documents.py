import io
import os
import re

from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends, File, Request, UploadFile, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional

from api.limiter import limiter

_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
_ALLOWED_MIME_TYPES = {"application/pdf"}


def _safe_filename(name: str) -> str:
    """Strip path components and non-safe characters from a filename."""
    name = os.path.basename(name)
    name = re.sub(r"[^\w.\-]", "_", name)
    return name or "document.pdf"

from api.db import InsuranceDocument
from api.domain.exceptions import LlmUnavailableError
from api.services.documents import (
    store_insurance_document,
    remove_insurance_document,
    get_document_keypoints,
    answer_document_question,
    compare_two_documents,
    find_similar_documents,
)
from api.schemas import (
    DocChatRequest,
    DocCompareRequest,
    DocumentChatOut,
    DocumentCompareOut,
    DocumentKeypointsOut,
)
from api.db import SessionLocal
from api.dependencies import get_db
from api.services.audit import log_audit

router = APIRouter()


def _auto_analyze_background(doc_id: int) -> None:
    """Background task wrapper — own DB session, never raises."""
    import logging
    db = SessionLocal()
    try:
        from api.services.documents import auto_analyze_document
        auto_analyze_document(doc_id, db)
    except Exception as exc:
        logging.getLogger(__name__).warning("Doc intel background failed for %d: %s", doc_id, exc)
    finally:
        db.close()


@router.post("/insurance-documents")
@limiter.limit("30/minute")
async def upload_insurance_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(...),
    category: str = Form("annet"),
    insurer: str = Form(""),
    year: Optional[int] = Form(None),
    period: str = Form("aktiv"),
    orgnr: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    db: Session = Depends(get_db),
) -> dict:
    """Upload and store an insurance document PDF."""
    if file.content_type not in _ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, detail="Only PDF files are accepted")
    pdf_bytes = await file.read()
    if len(pdf_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 50 MB limit")
    safe_name = _safe_filename(file.filename or "document.pdf")
    try:
        doc = store_insurance_document(
            pdf_bytes=pdf_bytes,
            filename=safe_name,
            title=title,
            category=category,
            insurer=insurer,
            year=year,
            period=period,
            orgnr=orgnr,
            db=db,
            tags=tags,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    log_audit(db, "document.upload", orgnr=orgnr,
              detail={"title": title, "doc_id": doc.id})
    # Auto-analyze in the background: extract keypoints, parse structured
    # tilbud data, and auto-compare if 2+ documents exist for the same orgnr.
    background_tasks.add_task(_auto_analyze_background, doc.id)
    return {
        "id": doc.id,
        "title": doc.title,
        "filename": doc.filename,
        "category": doc.category,
        "insurer": doc.insurer,
        "year": doc.year,
        "period": doc.period,
        "tags": doc.tags,
    }


@router.get("/insurance-documents")
def list_insurance_documents(
    category: Optional[str] = None,
    year: Optional[int] = None,
    period: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list:
    """List all insurance documents (no PDF bytes)."""
    q = db.query(InsuranceDocument)
    if category:
        q = q.filter(InsuranceDocument.category == category)
    if year:
        q = q.filter(InsuranceDocument.year == year)
    if period:
        q = q.filter(InsuranceDocument.period == period)
    docs = q.order_by(InsuranceDocument.uploaded_at.desc()).all()
    return [
        {
            "id": d.id,
            "title": d.title,
            "filename": d.filename,
            "category": d.category,
            "insurer": d.insurer,
            "year": d.year,
            "period": d.period,
            "orgnr": d.orgnr,
            "uploaded_at": d.uploaded_at,
            "tags": d.tags,
        }
        for d in docs
    ]


@router.get("/insurance-documents/{doc_id}/pdf")
def download_insurance_document_pdf(doc_id: int, db: Session = Depends(get_db)):
    """Serve the raw PDF bytes for an insurance document."""
    doc = db.query(InsuranceDocument).filter(InsuranceDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    safe_name = (doc.filename or f"document_{doc_id}.pdf").replace(" ", "_")
    return StreamingResponse(
        io.BytesIO(doc.pdf_content),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe_name}"'},
    )


@router.get(
    "/insurance-documents/{doc_id}/keypoints",
    response_model=DocumentKeypointsOut,
)
def get_document_keypoints_endpoint(doc_id: int, db: Session = Depends(get_db)):
    """Extract key points from an insurance document using LLM or heuristics."""
    doc = db.query(InsuranceDocument).filter(InsuranceDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"doc_id": doc_id, "title": doc.title, **get_document_keypoints(doc)}


@router.get("/insurance-documents/{doc_id}/similar")
def get_similar_documents(doc_id: int, db: Session = Depends(get_db)) -> list:
    """Return top-3 most similar insurance documents by text embedding cosine distance."""
    doc = db.query(InsuranceDocument).filter(InsuranceDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return find_similar_documents(doc, db)


@router.delete("/insurance-documents/{doc_id}")
def delete_insurance_document(doc_id: int, db: Session = Depends(get_db)) -> dict:
    if not remove_insurance_document(doc_id, db):
        raise HTTPException(status_code=404, detail="Document not found")
    log_audit(db, "document.delete", detail={"doc_id": doc_id})
    return {"deleted": doc_id}


@router.post(
    "/insurance-documents/{doc_id}/chat",
    response_model=DocumentChatOut,
)
def chat_with_document(doc_id: int, body: DocChatRequest, db: Session = Depends(get_db)):
    """Ask a question about an insurance document using Gemini native PDF understanding."""
    doc = db.query(InsuranceDocument).filter(InsuranceDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        answer = answer_document_question(doc, body.question)
    except LlmUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"doc_id": doc_id, "question": body.question, "answer": answer}


@router.post(
    "/insurance-documents/compare",
    response_model=DocumentCompareOut,
)
def compare_insurance_documents(body: DocCompareRequest, db: Session = Depends(get_db)) -> dict:
    """Compare two insurance documents using Gemini native PDF understanding."""
    if len(body.doc_ids) != 2:
        raise HTTPException(status_code=400, detail="Oppgi nøyaktig 2 dokument-IDer")
    docs = db.query(InsuranceDocument).filter(InsuranceDocument.id.in_(body.doc_ids)).all()
    if len(docs) != 2:
        raise HTTPException(status_code=404, detail="Ett eller begge dokumenter ikke funnet")

    id_order = {v: i for i, v in enumerate(body.doc_ids)}
    a, b = sorted(docs, key=lambda d: id_order.get(d.id, 0))

    try:
        structured = compare_two_documents(a, b)
    except LlmUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {
        "doc_a": {"id": a.id, "title": a.title},
        "doc_b": {"id": b.id, "title": b.title},
        "structured": structured,
    }

