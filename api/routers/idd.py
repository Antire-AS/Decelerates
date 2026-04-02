"""IDD (Insurance Distribution Directive) compliance endpoints.

Covers behovsanalyse (needs assessment) as required by
forsikringsformidlingsloven §§ 5-4, 7-1 to 7-10 and
Finanstilsynet circular 9/2019.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.db import IddBehovsanalyse
from api.dependencies import get_db
from api.schemas import IddBehovsanalyseIn

router = APIRouter()


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


@router.get("/org/{orgnr}/idd")
def list_behovsanalyser(
    orgnr: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    """List all behovsanalyser for a company (newest first)."""
    rows = (
        db.query(IddBehovsanalyse)
        .filter(IddBehovsanalyse.orgnr == orgnr, IddBehovsanalyse.firm_id == user.firm_id)
        .order_by(IddBehovsanalyse.created_at.desc())
        .all()
    )
    return [_serialize(r) for r in rows]


@router.post("/org/{orgnr}/idd", status_code=201)
def create_behovsanalyse(
    orgnr: str,
    body: IddBehovsanalyseIn,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Create a new IDD behovsanalyse for a company."""
    row = IddBehovsanalyse(
        orgnr=orgnr,
        firm_id=user.firm_id,
        created_by_email=user.email,
        created_at=datetime.now(timezone.utc),
        **body.model_dump(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize(row)


@router.get("/org/{orgnr}/idd/{idd_id}")
def get_behovsanalyse(
    orgnr: str,
    idd_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    row = db.query(IddBehovsanalyse).filter(
        IddBehovsanalyse.id == idd_id,
        IddBehovsanalyse.orgnr == orgnr,
        IddBehovsanalyse.firm_id == user.firm_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Behovsanalyse not found")
    return _serialize(row)


@router.delete("/org/{orgnr}/idd/{idd_id}", status_code=204)
def delete_behovsanalyse(
    orgnr: str,
    idd_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    row = db.query(IddBehovsanalyse).filter(
        IddBehovsanalyse.id == idd_id,
        IddBehovsanalyse.orgnr == orgnr,
        IddBehovsanalyse.firm_id == user.firm_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Behovsanalyse not found")
    db.delete(row)
    db.commit()
