from typing import Optional

import requests
from fastapi import APIRouter, Query, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from services import fetch_enhetsregisteret, fetch_finanstilsynet_licenses, fetch_org_profile, _auto_extract_pdf_sources, list_companies as _list_companies
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
    return _list_companies(limit, kommune, db)


@router.get("/org-by-name")
def get_org_by_name(
    name: str = Query(..., min_length=2),
    kommunenummer: Optional[str] = None,
    background_tasks: BackgroundTasks = None,
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
    return get_org_profile(orgnr=orgnr, background_tasks=background_tasks, db=db)
