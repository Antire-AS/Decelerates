"""Insurer entity and submission tracking endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.db import Insurer, Submission
from api.dependencies import get_db
from api.domain.exceptions import NotFoundError
from api.schemas import (
    InsurerIn,
    InsurerOut,
    InsurerUpdate,
    SubmissionIn,
    SubmissionOut,
    SubmissionUpdate,
)
from api.services.audit import log_audit
from api.services.insurer_service import InsurerService

router = APIRouter()


def _get_svc(db: Session = Depends(get_db)) -> InsurerService:
    return InsurerService(db)


def _serialize_insurer(
    row: Insurer,
    last_contact_at=None,
    avg_response_days: float | None = None,
) -> dict:
    return {
        "id": row.id,
        "firm_id": row.firm_id,
        "name": row.name,
        "org_number": row.org_number,
        "contact_name": row.contact_name,
        "contact_email": row.contact_email,
        "contact_phone": row.contact_phone,
        "appetite": row.appetite or [],
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "last_contact_at": (
            last_contact_at.isoformat()
            if last_contact_at is not None and hasattr(last_contact_at, "isoformat")
            else None
        ),
        "avg_response_days": avg_response_days,
    }


def _serialize_submission(row: Submission, insurer_name: str | None = None) -> dict:
    return {
        "id": row.id,
        "orgnr": row.orgnr,
        "insurer_id": row.insurer_id,
        "insurer_name": insurer_name,
        "product_type": row.product_type,
        "requested_at": row.requested_at.isoformat() if row.requested_at else None,
        "status": row.status.value if row.status else "pending",
        "premium_offered_nok": row.premium_offered_nok,
        "notes": row.notes,
        "created_by_email": row.created_by_email,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


# ── Insurer CRUD ──────────────────────────────────────────────────────────────


def _last_contact_by_name(db: Session, firm_id: int) -> dict[str, object]:
    """max(sent_at) per recipient.insurer_name, scoped to one firm.
    Lowercased name is the key — TenderRecipient.insurer_name is free text
    the broker picked, so casing/whitespace drift from the canonical Insurer
    name is common and we normalise both sides at lookup time."""
    from sqlalchemy import func
    from api.models.tender import Tender, TenderRecipient

    rows = (
        db.query(
            func.lower(TenderRecipient.insurer_name),
            func.max(TenderRecipient.sent_at),
        )
        .join(Tender, TenderRecipient.tender_id == Tender.id)
        .filter(Tender.firm_id == firm_id)
        .filter(TenderRecipient.sent_at.is_not(None))
        .group_by(func.lower(TenderRecipient.insurer_name))
        .all()
    )
    return {nm: ts for nm, ts in rows}


def _avg_response_days_by_name(db: Session, firm_id: int) -> dict[str, float]:
    """Average days between sent_at and response_at per insurer name."""
    from sqlalchemy import func
    from api.models.tender import Tender, TenderRecipient

    rows = (
        db.query(
            func.lower(TenderRecipient.insurer_name),
            func.avg(
                func.extract(
                    "epoch",
                    TenderRecipient.response_at - TenderRecipient.sent_at,
                )
            ),
        )
        .join(Tender, TenderRecipient.tender_id == Tender.id)
        .filter(Tender.firm_id == firm_id)
        .filter(TenderRecipient.response_at.is_not(None))
        .filter(TenderRecipient.sent_at.is_not(None))
        .group_by(func.lower(TenderRecipient.insurer_name))
        .all()
    )
    return {nm: float(secs) / 86400.0 for nm, secs in rows if secs is not None}


@router.get("/insurers", response_model=list[InsurerOut])
def list_insurers(
    user: CurrentUser = Depends(get_current_user),
    svc: InsurerService = Depends(_get_svc),
    db: Session = Depends(get_db),
) -> list:
    rows = svc.list_insurers(user.firm_id)
    if not rows:
        return []
    last_contact = _last_contact_by_name(db, user.firm_id)
    avg_response = _avg_response_days_by_name(db, user.firm_id)
    return [
        _serialize_insurer(
            r,
            last_contact_at=last_contact.get(r.name.lower()),
            avg_response_days=avg_response.get(r.name.lower()),
        )
        for r in rows
    ]


@router.post("/insurers", status_code=201)
def create_insurer(
    body: InsurerIn,
    user: CurrentUser = Depends(get_current_user),
    svc: InsurerService = Depends(_get_svc),
    db: Session = Depends(get_db),
) -> dict:
    row = svc.create_insurer(user.firm_id, body.model_dump())
    log_audit(db, "insurer.create", detail={"insurer_id": row.id, "name": body.name})
    return _serialize_insurer(row)


@router.put("/insurers/{insurer_id}")
def update_insurer(
    insurer_id: int,
    body: InsurerUpdate,
    user: CurrentUser = Depends(get_current_user),
    svc: InsurerService = Depends(_get_svc),
    db: Session = Depends(get_db),
) -> dict:
    try:
        row = svc.update_insurer(
            user.firm_id, insurer_id, body.model_dump(exclude_none=True)
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Insurer not found")
    log_audit(db, "insurer.update", detail={"insurer_id": insurer_id})
    return _serialize_insurer(row)


@router.delete("/insurers/{insurer_id}", status_code=204)
def delete_insurer(
    insurer_id: int,
    user: CurrentUser = Depends(get_current_user),
    svc: InsurerService = Depends(_get_svc),
    db: Session = Depends(get_db),
) -> None:
    try:
        svc.delete_insurer(user.firm_id, insurer_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Insurer not found")
    log_audit(db, "insurer.delete", detail={"insurer_id": insurer_id})


# ── Submission CRUD ───────────────────────────────────────────────────────────


@router.get("/org/{orgnr}/submissions", response_model=list[SubmissionOut])
def list_submissions(
    orgnr: str,
    user: CurrentUser = Depends(get_current_user),
    svc: InsurerService = Depends(_get_svc),
) -> list:
    return [
        _serialize_submission(r, name)
        for r, name in svc.list_submissions_enriched(orgnr, user.firm_id)
    ]


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
    log_audit(
        db,
        "submission.create",
        orgnr=orgnr,
        detail={"submission_id": row.id, "insurer_id": row.insurer_id},
    )
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
        row = svc.update_submission(
            user.firm_id, submission_id, body.model_dump(exclude_none=True)
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Submission not found")
    insurer = db.query(Insurer).filter(Insurer.id == row.insurer_id).first()
    log_audit(db, "submission.update", detail={"submission_id": submission_id})
    return _serialize_submission(row, insurer.name if insurer else None)


@router.delete("/submissions/{submission_id}", status_code=204)
def delete_submission(
    submission_id: int,
    user: CurrentUser = Depends(get_current_user),
    svc: InsurerService = Depends(_get_svc),
    db: Session = Depends(get_db),
) -> None:
    try:
        svc.delete_submission(user.firm_id, submission_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Submission not found")
    log_audit(db, "submission.delete", detail={"submission_id": submission_id})


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
    db: Session = Depends(get_db),
) -> dict:
    """Generate a professional Norwegian submission email to the insurer via LLM."""
    try:
        draft = svc.draft_submission_email(user.firm_id, submission_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Submission not found")
    log_audit(db, "submission.draft_email", detail={"submission_id": submission_id})
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
    result = recommend_insurers(orgnr, user.firm_id, product_types, db)
    log_audit(
        db, "recommend.create", orgnr=orgnr, detail={"product_types": product_types}
    )
    return result
