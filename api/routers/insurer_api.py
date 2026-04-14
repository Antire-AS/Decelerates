"""Public Insurer API — external insurers submit quotes and view submissions.

Authentication is via X-API-Key header matched against Insurer.api_key.
This is separate from the broker's Azure AD auth — insurers are external
parties with their own API key per insurer entity.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.db import Insurer, Submission, SubmissionStatus
from api.dependencies import get_db
from api.services.audit import log_audit

router = APIRouter(prefix="/api/v1", tags=["insurer-api"])


# ── API key auth dependency ──────────────────────────────────────────────────

def verify_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> Insurer:
    """Validate the X-API-Key header against Insurer.api_key.

    Returns the authenticated Insurer row. Raises 401 if no match.
    """
    if not x_api_key or not x_api_key.strip():
        raise HTTPException(status_code=401, detail="Missing API key")
    insurer = (
        db.query(Insurer)
        .filter(Insurer.api_key == x_api_key.strip())
        .first()
    )
    if not insurer:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return insurer


# ── Request / response schemas ───────────────────────────────────────────────

class QuoteSubmit(BaseModel):
    submission_id: int
    premium_offered_nok: float
    notes: str | None = None


class QuoteResponse(BaseModel):
    submission_id: int
    status: str
    premium_offered_nok: float | None
    updated_at: str


class SubmissionView(BaseModel):
    id: int
    orgnr: str
    product_type: str
    requested_at: str | None
    status: str
    notes: str | None


# ── Endpoints ────────────────────────────────────────────────────────────────

def _get_submission_for_insurer(db: Session, submission_id: int, insurer_id: int) -> Submission:
    """Look up a submission that belongs to the given insurer, or raise 404."""
    sub = db.query(Submission).filter(
        Submission.id == submission_id, Submission.insurer_id == insurer_id,
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found or not assigned to this insurer")
    return sub


@router.post("/quotes", response_model=QuoteResponse)
def submit_quote(
    body: QuoteSubmit, db: Session = Depends(get_db),
    insurer: Insurer = Depends(verify_api_key),
) -> dict:
    """Insurer submits a quote (premium) for a submission they received."""
    submission = _get_submission_for_insurer(db, body.submission_id, insurer.id)
    submission.premium_offered_nok = body.premium_offered_nok
    submission.status = SubmissionStatus.quoted
    if body.notes:
        submission.notes = f"{submission.notes or ''}\n[Insurer quote]: {body.notes}".strip()
    log_audit(db, "insurer_api.quote", orgnr=submission.orgnr,
              detail={"submission_id": submission.id, "insurer_id": insurer.id, "premium_nok": body.premium_offered_nok})
    return {"submission_id": submission.id, "status": submission.status.value,
            "premium_offered_nok": submission.premium_offered_nok, "updated_at": datetime.now(timezone.utc).isoformat()}


@router.get("/submissions/{submission_id}", response_model=SubmissionView)
def get_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    insurer: Insurer = Depends(verify_api_key),
) -> dict:
    """Insurer views a submission they received."""
    submission = _get_submission_for_insurer(db, submission_id, insurer.id)
    return {
        "id": submission.id,
        "orgnr": submission.orgnr,
        "product_type": submission.product_type,
        "requested_at": submission.requested_at.isoformat() if submission.requested_at else None,
        "status": submission.status.value if submission.status else "pending",
        "notes": submission.notes,
    }
