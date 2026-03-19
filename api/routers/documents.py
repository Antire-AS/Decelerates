import io
import os
import uuid

from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional

from api.db import InsuranceDocument, CompanyChunk
from api.domain.exceptions import LlmUnavailableError
from api.services.documents import (
    store_insurance_document,
    remove_insurance_document,
    get_document_keypoints,
    answer_document_question,
    compare_two_documents,
)
from api.services.llm import _embed
from api.services.blob_storage import BlobStorageService
from api.schemas import DocChatRequest, DocCompareRequest
from api.dependencies import get_db

_ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/x-msvideo"}
_VIDEOS_CONTAINER = os.getenv("AZURE_VIDEO_CONTAINER", "transksrt")

router = APIRouter()


@router.post("/insurance-documents")
async def upload_insurance_document(
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
    pdf_bytes = await file.read()
    try:
        doc = store_insurance_document(
            pdf_bytes=pdf_bytes,
            filename=file.filename or "document.pdf",
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


@router.get("/insurance-documents/{doc_id}/keypoints")
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
    text = (doc.extracted_text or "")[:2000]
    if not text:
        return []
    embedding = _embed(text)
    if not embedding:
        return []
    others = (
        db.query(InsuranceDocument)
        .filter(InsuranceDocument.id != doc_id, InsuranceDocument.extracted_text.isnot(None))
        .all()
    )
    scored = []
    for other in others:
        other_emb = _embed((other.extracted_text or "")[:2000])
        if not other_emb:
            continue
        dot = sum(a * b for a, b in zip(embedding, other_emb))
        norm_a = sum(x * x for x in embedding) ** 0.5
        norm_b = sum(x * x for x in other_emb) ** 0.5
        sim = dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
        scored.append({"id": other.id, "title": other.title, "similarity": round(sim, 4)})
    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:3]


@router.delete("/insurance-documents/{doc_id}")
def delete_insurance_document(doc_id: int, db: Session = Depends(get_db)) -> dict:
    if not remove_insurance_document(doc_id, db):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": doc_id}


@router.post("/insurance-documents/{doc_id}/chat")
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


@router.post("/insurance-documents/compare")
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


# ── Video endpoints ────────────────────────────────────────────────────────────

@router.post("/videos/upload")
async def upload_video(file: UploadFile = File(...)) -> dict:
    """Upload a video file to Azure Blob Storage 'videos' container."""
    content_type = file.content_type or ""
    if content_type not in _ALLOWED_VIDEO_TYPES:
        raise HTTPException(status_code=400, detail="Filtype ikke støttet. Bruk .mp4, .mov eller .avi")
    video_bytes = await file.read()
    blob_name = f"{uuid.uuid4()}_{file.filename}"
    svc = BlobStorageService()
    if not svc.is_configured():
        raise HTTPException(status_code=503, detail="Blob Storage ikke konfigurert (AZURE_BLOB_ENDPOINT mangler)")
    url = svc.upload(_VIDEOS_CONTAINER, blob_name, video_bytes)
    if not url:
        raise HTTPException(status_code=502, detail="Opplasting til Blob Storage feilet")
    return {"blob_name": blob_name, "url": url, "filename": file.filename}


@router.get("/videos")
def list_videos() -> list:
    """List all videos in Azure Blob Storage 'videos' container."""
    svc = BlobStorageService()
    if not svc.is_configured():
        return []
    try:
        from azure.storage.blob import BlobServiceClient
        from azure.identity import DefaultAzureCredential
        import os
        client = BlobServiceClient(
            account_url=os.getenv("AZURE_BLOB_ENDPOINT", ""),
            credential=DefaultAzureCredential(),
        )
        container = client.get_container_client(_VIDEOS_CONTAINER)
        return [
            {"blob_name": b.name, "url": f"{os.getenv('AZURE_BLOB_ENDPOINT', '')}/{_VIDEOS_CONTAINER}/{b.name}"}
            for b in container.list_blobs()
        ]
    except Exception:
        return []
