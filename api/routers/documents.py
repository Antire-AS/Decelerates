import io
import os
import re
import uuid

from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Form, Request
from fastapi.responses import StreamingResponse, Response
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
    """List MP4 videos with chapter metadata. Blobs may be in subdirectories."""
    import posixpath
    svc = BlobStorageService()
    if not svc.is_configured():
        return []
    all_blobs = set(svc.list_blobs(_VIDEOS_CONTAINER))
    mp4s = sorted(b for b in all_blobs if b.lower().endswith(".mp4"))
    results = []
    for mp4 in mp4s:
        directory = posixpath.dirname(mp4)
        fname = posixpath.basename(mp4)[:-4]          # e.g. ffs080524_subs
        fname_clean = fname.removesuffix("_subs")     # e.g. ffs080524
        display_name = fname_clean.replace("_", " ")

        # Sections: look for {fname}.json, {fname}_sections.json in same dir
        sections = None
        base = mp4[:-4]
        for cand in [f"{base}.json", f"{base}_sections.json", f"{base}_timeline.json",
                     f"{directory}/{fname_clean}_sections.json",
                     f"{directory}/{fname_clean}_timeline.json"]:
            if cand in all_blobs:
                sections = svc.download_json(_VIDEOS_CONTAINER, cand)
                break

        # Thumbnail: look for sprite jpg in thumbnails/ subdir or same dir
        thumb_candidates = [
            f"{directory}/thumbnails/{fname}_sprite.jpg",
            f"{directory}/thumbnails/{fname}.jpg",
            f"{base}.jpg",
        ]
        thumb_blob = next((c for c in thumb_candidates if c in all_blobs), None)
        thumbnail_url = svc.generate_sas_url(_VIDEOS_CONTAINER, thumb_blob) if thumb_blob else None
        results.append({
            "blob_name": mp4,
            "filename": display_name,
            "sections": sections,
            "thumbnail_url": thumbnail_url,
        })
    return results


@router.get("/videos/stream")
async def stream_video(blob: str, request: Request):
    """Stream a video blob with HTTP range request support. blob= query param is the blob name."""
    svc = BlobStorageService()
    if not svc.is_configured():
        raise HTTPException(status_code=503, detail="Blob Storage ikke konfigurert")
    file_size = svc.get_blob_size(_VIDEOS_CONTAINER, blob)
    if file_size is None:
        raise HTTPException(status_code=404, detail="Video ikke funnet")
    range_header = request.headers.get("range")
    if range_header:
        m = re.match(r"bytes=(\d*)-(\d*)", range_header)
        start = int(m.group(1)) if m and m.group(1) else 0
        end = int(m.group(2)) if m and m.group(2) else file_size - 1
        length = end - start + 1
        chunks = svc.stream_range(_VIDEOS_CONTAINER, blob, offset=start, length=length)
        if chunks is None:
            raise HTTPException(status_code=502)
        return StreamingResponse(
            chunks, status_code=206, media_type="video/mp4",
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(length),
            },
        )
    chunks = svc.stream_range(_VIDEOS_CONTAINER, blob)
    if chunks is None:
        raise HTTPException(status_code=502)
    return StreamingResponse(
        chunks, media_type="video/mp4",
        headers={"Accept-Ranges": "bytes", "Content-Length": str(file_size)},
    )
