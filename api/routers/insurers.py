"""Insurer entity and submission tracking endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.db import Insurer, Submission
from api.dependencies import get_db
from api.domain.exceptions import NotFoundError
from api.schemas import InsurerIn, InsurerOut, InsurerUpdate, SubmissionIn, SubmissionOut, SubmissionUpdate
from api.services.insurer_service import InsurerService

router = APIRouter()


def _get_svc(db: Session = Depends(get_db)) -> InsurerService:
    return InsurerService(db)


def _serialize_insurer(row: Insurer) -> dict:
    return {
        "id":            row.id,
        "firm_id":       row.firm_id,
        "name":          row.name,
        "org_number":    row.org_number,
        "contact_name":  row.contact_name,
        "contact_email": row.contact_email,
        "contact_phone": row.contact_phone,
        "appetite":      row.appetite or [],
        "notes":         row.notes,
        "created_at":    row.created_at.isoformat() if row.created_at else None,
    }


def _serialize_submission(row: Submission, insurer_name: str | None = None) -> dict:
    return {
        "id":                  row.id,
        "orgnr":               row.orgnr,
        "insurer_id":          row.insurer_id,
        "insurer_name":        insurer_name,
        "product_type":        row.product_type,
        "requested_at":        row.requested_at.isoformat() if row.requested_at else None,
        "status":              row.status.value if row.status else "pending",
        "premium_offered_nok": row.premium_offered_nok,
        "notes":               row.notes,
        "created_by_email":    row.created_by_email,
        "created_at":          row.created_at.isoformat() if row.created_at else None,
    }


# ── Insurer CRUD ──────────────────────────────────────────────────────────────

@router.get("/insurers", response_model=list[InsurerOut])
def list_insurers(
    user: CurrentUser = Depends(get_current_user),
    svc: InsurerService = Depends(_get_svc),
) -> list:
    rows = svc.list_insurers(user.firm_id)
    return [_serialize_insurer(r) for r in rows]


@router.post("/insurers", status_code=201)
def create_insurer(
    body: InsurerIn,
    user: CurrentUser = Depends(get_current_user),
    svc: InsurerService = Depends(_get_svc),
) -> dict:
    row = svc.create_insurer(user.firm_id, body.model_dump())
    return _serialize_insurer(row)


@router.put("/insurers/{insurer_id}")
def update_insurer(
    insurer_id: int,
    body: InsurerUpdate,
    user: CurrentUser = Depends(get_current_user),
    svc: InsurerService = Depends(_get_svc),
) -> dict:
    try:
        row = svc.update_insurer(user.firm_id, insurer_id, body.model_dump(exclude_none=True))
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Insurer not found")
    return _serialize_insurer(row)


@router.delete("/insurers/{insurer_id}", status_code=204)
def delete_insurer(
    insurer_id: int,
    user: CurrentUser = Depends(get_current_user),
    svc: InsurerService = Depends(_get_svc),
) -> None:
    try:
        svc.delete_insurer(user.firm_id, insurer_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Insurer not found")


# ── Submission CRUD ───────────────────────────────────────────────────────────

@router.get("/org/{orgnr}/submissions", response_model=list[SubmissionOut])
def list_submissions(
    orgnr: str,
    user: CurrentUser = Depends(get_current_user),
    svc: InsurerService = Depends(_get_svc),
) -> list:
    return [_serialize_submission(r, name) for r, name in svc.list_submissions_enriched(orgnr, user.firm_id)]


@router.post("/org/{orgnr}/submissions", status_code=201)
def create_submission(
    orgnr: str,
    body: SubmissionIn,
    user: CurrentUser = Depends(get_current_user),
    svc: InsurerService = Depends(_get_svc),
    db: Session = Depends(get_db),
) -> dict:
    data = body.model_dump()
    row = svc.create_submission(orgnr, user.firm_id, user.email, data)
    insurer = db.query(Insurer).filter(Insurer.id == row.insurer_id).first()
    return _serialize_submission(row, insurer.name if insurer else None)


@router.put("/submissions/{submission_id}")
def update_submission(
    submission_id: int,
    body: SubmissionUpdate,
    user: CurrentUser = Depends(get_current_user),
    svc: InsurerService = Depends(_get_svc),
    db: Session = Depends(get_db),
) -> dict:
    try:
        row = svc.update_submission(user.firm_id, submission_id, body.model_dump(exclude_none=True))
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Submission not found")
    insurer = db.query(Insurer).filter(Insurer.id == row.insurer_id).first()
    return _serialize_submission(row, insurer.name if insurer else None)


@router.delete("/submissions/{submission_id}", status_code=204)
def delete_submission(
    submission_id: int,
    user: CurrentUser = Depends(get_current_user),
    svc: InsurerService = Depends(_get_svc),
) -> None:
    try:
        svc.delete_submission(user.firm_id, submission_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Submission not found")


# ── Analytics ────────────────────────────────────────────────────────────────

@router.get("/insurers/match", response_model=list[InsurerOut])
def match_appetite(
    product_type: str,
    user: CurrentUser = Depends(get_current_user),
    svc: InsurerService = Depends(_get_svc),
) -> list:
    """Insurers whose appetite matches the given product type, ranked by fit."""
    rows = svc.match_appetite(user.firm_id, product_type)
    return [_serialize_insurer(r) for r in rows]


@router.get("/insurers/win-loss")
def get_win_loss_summary(
    user: CurrentUser = Depends(get_current_user),
    svc: InsurerService = Depends(_get_svc),
) -> dict:
    """Win/loss analysis across all submissions for the firm."""
    return svc.get_win_loss_summary(user.firm_id)


@router.post("/submissions/{submission_id}/draft-email")
def draft_submission_email(
    submission_id: int,
    user: CurrentUser = Depends(get_current_user),
    svc: InsurerService = Depends(_get_svc),
) -> dict:
    """Generate a professional Norwegian submission email to the insurer via LLM."""
    try:
        draft = svc.draft_submission_email(user.firm_id, submission_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Submission not found")
    return {"submission_id": submission_id, "draft_email": draft}


# ── Insurer matching agent ────────────────────────────────────────────────────

@router.post("/org/{orgnr}/recommend-insurers")
def recommend_insurers_for_company(
    orgnr: str,
    body: dict | None = None,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Score and rank insurers for a company based on appetite, win rate, and profile.

    Optionally pass `{"product_types": ["Cyberforsikring", "Ansvarsforsikring"]}`
    in the request body. If omitted, product types are auto-derived from the
    company's coverage gap analysis.

    Returns top 3 recommended insurers with LLM-generated Norwegian reasoning.
    """
    from api.services.insurer_matching import recommend_insurers
    product_types = (body or {}).get("product_types")
    return recommend_insurers(orgnr, user.firm_id, product_types, db)
