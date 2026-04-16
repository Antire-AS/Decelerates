"""Coverage analysis endpoints — upload policy PDFs and get structured coverage breakdown."""
import logging
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from api.auth import get_current_user
from api.db import User
from api.dependencies import get_db
from api.limiter import limiter
from api.schemas import CoverageAnalysisOut
from api.services.coverage_service import CoverageService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["coverage-analysis"])

_MAX_PDF_BYTES = 50 * 1024 * 1024  # 50 MB


def _svc(db: Session = Depends(get_db)) -> CoverageService:
    return CoverageService(db)


@router.post("/org/{orgnr}/coverage/analyse", response_model=CoverageAnalysisOut)
@limiter.limit("10/minute")
async def analyse_coverage(
    request: Request,
    orgnr: str,
    file: UploadFile = File(...),
    title: str = Form(""),
    insurer: str = Form(""),
    product_type: str = Form(""),
    svc: CoverageService = Depends(_svc),
    user: User = Depends(get_current_user),
):
    """Upload a policy PDF and analyse its coverage with AI."""
    if file.content_type and file.content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="Kun PDF-filer er støttet")

    raw = await file.read()
    if len(raw) > _MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="Fil for stor (maks 50 MB)")

    safe_title = title or file.filename or "Ukjent dokument"
    analysis = svc.create_analysis(
        orgnr=orgnr,
        firm_id=user.firm_id,
        title=safe_title,
        pdf_bytes=raw,
        filename=file.filename or "policy.pdf",
        insurer=insurer or None,
        product_type=product_type or None,
    )

    # Run AI analysis in background job so the request doesn't block
    from api.services.job_queue_service import JobQueueService
    jq = JobQueueService(svc.db)
    jq.enqueue("coverage_analysis", {"analysis_id": analysis.id})

    return _to_out(analysis)


@router.get("/org/{orgnr}/coverage", response_model=List[CoverageAnalysisOut])
@limiter.limit("30/minute")
async def list_coverage(
    request: Request,
    orgnr: str,
    svc: CoverageService = Depends(_svc),
    user: User = Depends(get_current_user),
):
    """List all coverage analyses for a company."""
    return [_to_out(a) for a in svc.list_for_company(orgnr, user.firm_id)]


@router.get("/coverage/{analysis_id}", response_model=CoverageAnalysisOut)
@limiter.limit("30/minute")
async def get_coverage(
    request: Request,
    analysis_id: int,
    svc: CoverageService = Depends(_svc),
    user: User = Depends(get_current_user),
):
    """Get a single coverage analysis."""
    analysis = svc.get(analysis_id, user.firm_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analyse ikke funnet")
    return _to_out(analysis)


@router.delete("/coverage/{analysis_id}")
@limiter.limit("30/minute")
async def delete_coverage(
    request: Request,
    analysis_id: int,
    svc: CoverageService = Depends(_svc),
    user: User = Depends(get_current_user),
):
    """Delete a coverage analysis."""
    if not svc.delete(analysis_id, user.firm_id):
        raise HTTPException(status_code=404, detail="Analyse ikke funnet")
    return {"deleted": True}


def _to_out(a) -> dict:
    return {
        "id": a.id,
        "orgnr": a.orgnr,
        "title": a.title,
        "insurer": a.insurer,
        "product_type": a.product_type,
        "filename": a.filename,
        "coverage_data": a.coverage_data,
        "premium_nok": a.premium_nok,
        "deductible_nok": a.deductible_nok,
        "coverage_sum_nok": a.coverage_sum_nok,
        "status": a.status,
        "created_at": a.created_at,
    }
