"""IDD (Insurance Distribution Directive) compliance endpoints.

Covers behovsanalyse (needs assessment) as required by
forsikringsformidlingsloven §§ 5-4, 7-1 to 7-10 and
Finanstilsynet circular 9/2019.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.db import IddBehovsanalyse
from api.dependencies import get_db
from api.domain.exceptions import NotFoundError
from api.schemas import IddBehovsanalyseIn, IddBehovsanalyseOut
from api.services.idd import IddService

router = APIRouter()


def _get_idd_service(db: Session = Depends(get_db)) -> IddService:
    return IddService(db)


def _serialize(row: IddBehovsanalyse) -> dict:
    return {
        "id":                          row.id,
        "orgnr":                       row.orgnr,
        "created_by_email":            row.created_by_email,
        "created_at":                  row.created_at.isoformat() if row.created_at else None,
        "client_name":                 row.client_name,
        "client_contact_name":         row.client_contact_name,
        "client_contact_email":        row.client_contact_email,
        "existing_insurance":          row.existing_insurance or [],
        "risk_appetite":               row.risk_appetite,
        "property_owned":              row.property_owned,
        "has_employees":               row.has_employees,
        "has_vehicles":                row.has_vehicles,
        "has_professional_liability":  row.has_professional_liability,
        "has_cyber_risk":              row.has_cyber_risk,
        "annual_revenue_nok":          row.annual_revenue_nok,
        "special_requirements":        row.special_requirements,
        "recommended_products":        row.recommended_products or [],
        "advisor_notes":               row.advisor_notes,
        "suitability_basis":           row.suitability_basis,
        "fee_basis":                   row.fee_basis,
        "fee_amount_nok":              row.fee_amount_nok,
    }


@router.get("/org/{orgnr}/idd", response_model=list[IddBehovsanalyseOut])
def list_behovsanalyser(
    orgnr: str,
    user: CurrentUser = Depends(get_current_user),
    svc: IddService = Depends(_get_idd_service),
) -> list:
    """List all behovsanalyser for a company (newest first)."""
    return [_serialize(r) for r in svc.list(orgnr, user.firm_id)]


@router.post("/org/{orgnr}/idd", status_code=201)
def create_behovsanalyse(
    orgnr: str,
    body: IddBehovsanalyseIn,
    user: CurrentUser = Depends(get_current_user),
    svc: IddService = Depends(_get_idd_service),
) -> dict:
    """Create a new IDD behovsanalyse for a company."""
    row = svc.create(orgnr, user.firm_id, user.email, body.model_dump())
    return _serialize(row)


@router.get("/org/{orgnr}/idd/{idd_id}")
def get_behovsanalyse(
    orgnr: str,
    idd_id: int,
    user: CurrentUser = Depends(get_current_user),
    svc: IddService = Depends(_get_idd_service),
) -> dict:
    try:
        row = svc.get(orgnr, user.firm_id, idd_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Behovsanalyse not found")
    return _serialize(row)


@router.delete("/org/{orgnr}/idd/{idd_id}", status_code=204)
def delete_behovsanalyse(
    orgnr: str,
    idd_id: int,
    user: CurrentUser = Depends(get_current_user),
    svc: IddService = Depends(_get_idd_service),
) -> None:
    try:
        svc.delete(orgnr, user.firm_id, idd_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Behovsanalyse not found")


@router.post("/org/{orgnr}/idd/{idd_id}/generate-suitability")
def generate_suitability(
    orgnr: str,
    idd_id: int,
    user: CurrentUser = Depends(get_current_user),
    svc: IddService = Depends(_get_idd_service),
) -> dict:
    """Generate and store an LLM-written suitability justification for this behovsanalyse."""
    try:
        reasoning = svc.generate_suitability_reasoning(orgnr, user.firm_id, idd_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Behovsanalyse not found")
    return {"idd_id": idd_id, "suitability_basis": reasoning}
