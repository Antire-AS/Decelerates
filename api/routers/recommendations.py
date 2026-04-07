"""Recommendation letter endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.db import BrokerSettings, Company, IddBehovsanalyse, Recommendation, Submission
from api.dependencies import get_db
from api.domain.exceptions import NotFoundError
from api.schemas import RecommendationIn, SigningSessionOut
from api.services.pdf_recommendation import generate_recommendation_pdf
from api.services.recommendation_service import RecommendationService
from api.services.signicat_service import SignicatService

router = APIRouter()


def _get_svc(db: Session = Depends(get_db)) -> RecommendationService:
    return RecommendationService(db)


def _serialize(row: Recommendation) -> dict:
    return {
        "id":                  row.id,
        "orgnr":               row.orgnr,
        "created_by_email":    row.created_by_email,
        "created_at":          row.created_at.isoformat() if row.created_at else None,
        "idd_id":              row.idd_id,
        "submission_ids":      row.submission_ids or [],
        "recommended_insurer": row.recommended_insurer,
        "rationale_text":      row.rationale_text,
        "has_pdf":             row.pdf_content is not None,
    }


def _get_broker(db: Session) -> dict:
    row = db.query(BrokerSettings).filter(BrokerSettings.id == 1).first()
    if not row:
        return {}
    return {
        "firm_name":     row.firm_name,
        "contact_name":  row.contact_name,
        "contact_email": row.contact_email,
        "contact_phone": row.contact_phone,
    }


@router.get("/org/{orgnr}/recommendations")
def list_recommendations(
    orgnr: str,
    user: CurrentUser = Depends(get_current_user),
    svc: RecommendationService = Depends(_get_svc),
) -> list:
    return [_serialize(r) for r in svc.list(orgnr, user.firm_id)]


@router.post("/org/{orgnr}/recommendations", status_code=201)
def create_recommendation(
    orgnr: str,
    body: RecommendationIn,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    svc: RecommendationService = Depends(_get_svc),
) -> dict:
    idd_check = (
        db.query(IddBehovsanalyse)
        .filter(
            IddBehovsanalyse.orgnr == orgnr,
            IddBehovsanalyse.firm_id == user.firm_id,
        )
        .order_by(IddBehovsanalyse.created_at.desc())
        .first()
    )
    if not idd_check:
        raise HTTPException(
            status_code=422,
            detail="IDD behovsanalyse må fullføres før en anbefaling kan utstedes.",
        )

    company = db.query(Company).filter(Company.orgnr == orgnr).first()
    company_name = company.navn if company else orgnr

    row = svc.create(
        orgnr=orgnr,
        firm_id=user.firm_id,
        created_by_email=user.email,
        company_name=company_name,
        recommended_insurer=body.recommended_insurer,
        submission_ids=body.submission_ids,
        idd_id=body.idd_id,
        rationale_override=body.rationale_text,
    )
    return _serialize(row)


@router.get("/org/{orgnr}/recommendations/{rec_id}/pdf")
def get_recommendation_pdf(
    orgnr: str,
    rec_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    svc: RecommendationService = Depends(_get_svc),
) -> Response:
    try:
        row = svc.get(orgnr, user.firm_id, rec_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    if row.pdf_content:
        pdf_bytes = row.pdf_content
    else:
        company = db.query(Company).filter(Company.orgnr == orgnr).first()
        company_name = company.navn if company else orgnr
        broker = _get_broker(db)

        submission_dicts = []
        if row.submission_ids:
            subs = db.query(Submission).filter(Submission.id.in_(row.submission_ids)).all()
            from api.db import Insurer
            insurer_map = {
                i.id: i.name
                for i in db.query(Insurer).filter(
                    Insurer.id.in_([s.insurer_id for s in subs])
                ).all()
            }
            submission_dicts = [
                {
                    "insurer_name":        insurer_map.get(s.insurer_id, "–"),
                    "product_type":        s.product_type,
                    "premium_offered_nok": s.premium_offered_nok,
                    "status":              s.status.value if s.status else "pending",
                    "requested_at":        s.requested_at.isoformat() if s.requested_at else None,
                }
                for s in subs
            ]

        pdf_bytes = generate_recommendation_pdf(
            orgnr=orgnr,
            company_name=company_name,
            recommended_insurer=row.recommended_insurer or "",
            rationale_text=row.rationale_text or "",
            submissions=submission_dicts,
            broker=broker,
            created_by_email=row.created_by_email,
        )
        svc.store_pdf(rec_id, pdf_bytes)

    filename = f"anbefaling_{orgnr}_{rec_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/org/{orgnr}/recommendations/{rec_id}", status_code=204)
def delete_recommendation(
    orgnr: str,
    rec_id: int,
    user: CurrentUser = Depends(get_current_user),
    svc: RecommendationService = Depends(_get_svc),
) -> None:
    try:
        svc.delete(orgnr, user.firm_id, rec_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Recommendation not found")


def _resolve_signable_recommendation(
    svc: RecommendationService, orgnr: str, firm_id: int, rec_id: int,
) -> Recommendation:
    """Fetch a recommendation that's ready to sign — must exist and have a PDF.
    Extracted so the route handler stays under 40 lines."""
    try:
        row = svc.get(orgnr, firm_id, rec_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    if not row.pdf_content:
        raise HTTPException(
            status_code=409,
            detail="Generer PDF først (kall GET /org/{orgnr}/recommendations/{rec_id}/pdf).",
        )
    return row


@router.post(
    "/org/{orgnr}/recommendations/{rec_id}/sign",
    response_model=SigningSessionOut,
)
def sign_recommendation(
    orgnr: str,
    rec_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    svc: RecommendationService = Depends(_get_svc),
) -> dict:
    """Plan §🟢 #11 — create a Signicat signing session."""
    signicat = SignicatService()
    if not signicat.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Signicat er ikke konfigurert. Sett SIGNICAT_* env vars.",
        )
    row = _resolve_signable_recommendation(svc, orgnr, user.firm_id, rec_id)
    company = db.query(Company).filter(Company.orgnr == orgnr).first()
    company_name = company.navn if company else orgnr
    try:
        session = signicat.create_signing_session(
            pdf_bytes=bytes(row.pdf_content),
            signer_email=user.email,
            signer_name=user.name,
            document_title=f"Anbefalingsbrev — {company_name}",
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Signicat feilet: {exc}")
    svc.attach_signing_session(rec_id, session["session_id"])
    return session
