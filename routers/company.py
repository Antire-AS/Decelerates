from typing import Optional

import requests
from fastapi import APIRouter, Query, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from db import Company
from services import fetch_enhetsregisteret, fetch_finanstilsynet_licenses, fetch_org_profile, _auto_extract_pdf_sources
from dependencies import get_db

router = APIRouter()


@router.get("/ping")
def ping():
    return {"status": "ok"}


@router.get("/search")
def search_orgs(
    name: str = Query(..., min_length=2),
    kommunenummer: Optional[str] = None,
    size: int = Query(20, ge=1, le=100),
):
    try:
        return fetch_enhetsregisteret(name=name, kommunenummer=kommunenummer, size=size)
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/org/{orgnr}")
def get_org_profile(
    orgnr: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        result = fetch_org_profile(orgnr, db)
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if result is None:
        raise HTTPException(status_code=404, detail="Organisation not found")

    # Phase 1 + Phase 2 background PDF extraction.
    # Pass org dict so Phase 2 discovery has access to navn + hjemmeside if needed.
    org = (result or {}).get("org")
    background_tasks.add_task(_auto_extract_pdf_sources, orgnr, org)

    return result


@router.get("/org/{orgnr}/licenses")
def get_org_licenses(orgnr: str):
    try:
        licenses = fetch_finanstilsynet_licenses(orgnr)
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {"orgnr": orgnr, "licenses": licenses}


@router.get("/companies")
def list_companies(
    limit: int = Query(50, ge=1, le=500),
    kommune: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Company)
    if kommune:
        q = q.filter(Company.kommune == kommune)

    rows = q.order_by(Company.id.desc()).limit(limit).all()

    return [
        {
            "id": c.id,
            "orgnr": c.orgnr,
            "navn": c.navn,
            "organisasjonsform_kode": c.organisasjonsform_kode,
            "kommune": c.kommune,
            "land": c.land,
            "naeringskode1": c.naeringskode1,
            "naeringskode1_beskrivelse": c.naeringskode1_beskrivelse,
            "regnskapsår": c.regnskapsår,
            "omsetning": c.sum_driftsinntekter,
            "sum_eiendeler": c.sum_eiendeler,
            "sum_egenkapital": c.sum_egenkapital,
            "egenkapitalandel": c.equity_ratio,
            "risk_score": c.risk_score,
        }
        for c in rows
    ]


@router.get("/org-by-name")
def get_org_by_name(
    name: str = Query(..., min_length=2),
    kommunenummer: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Søk på navn, ta første treff, og returner samme som /org/{orgnr}.
    Brukes som komfort-endepunkt (ikke perfekt matching).
    """
    candidates = fetch_enhetsregisteret(name=name, kommunenummer=kommunenummer, size=1)
    if not candidates:
        raise HTTPException(status_code=404, detail="No organisation found for name")

    orgnr = candidates[0]["orgnr"]
    return get_org_profile(orgnr=orgnr, db=db)
