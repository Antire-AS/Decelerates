"""Org-enrichment utility endpoints — BRREG enrichment, geocoding, benchmarks, exchange rates.

Admin, debug, and notification endpoints have been extracted to admin_router.py.
"""
import requests
from fastapi import APIRouter, HTTPException

from api.services import (
    fetch_enhet_by_orgnr,
    fetch_koordinater,
    fetch_losore,
    fetch_ssb_benchmark,
    fetch_company_struktur,
    fetch_norgesbank_rate,
    fetch_board_members,
    _generate_synthetic_financials,
)

router = APIRouter()


@router.get("/org/{orgnr}/roles")
def get_org_roles(orgnr: str) -> dict:
    try:
        members = fetch_board_members(orgnr)
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"orgnr": orgnr, "members": members}


@router.get("/org/{orgnr}/estimate")
def get_synthetic_estimate(orgnr: str) -> dict:
    org_data = fetch_enhet_by_orgnr(orgnr)
    if not org_data:
        raise HTTPException(status_code=404, detail="Organisation not found")
    result = _generate_synthetic_financials(org_data)
    if not result:
        raise HTTPException(
            status_code=503,
            detail="No LLM API key configured or generation failed",
        )
    return {"orgnr": orgnr, "estimated": result}


@router.get("/org/{orgnr}/bankruptcy")
def get_bankruptcy_status(orgnr: str) -> dict:
    org = fetch_enhet_by_orgnr(orgnr)
    if not org:
        raise HTTPException(status_code=404, detail="Organisation not found")
    return {
        "orgnr": orgnr,
        "konkurs": org.get("konkurs", False),
        "under_konkursbehandling": org.get("under_konkursbehandling", False),
        "under_avvikling": org.get("under_avvikling", False),
    }


@router.get("/org/{orgnr}/koordinater")
def get_koordinater(orgnr: str) -> dict:
    org = fetch_enhet_by_orgnr(orgnr)
    if not org:
        raise HTTPException(status_code=404, detail="Organisation not found")
    coords = fetch_koordinater(org)
    return {"orgnr": orgnr, "coordinates": coords}


@router.get("/org/{orgnr}/losore")
def get_losore(orgnr: str) -> dict:
    result = fetch_losore(orgnr)
    return {"orgnr": orgnr, **result}


@router.get("/org/{orgnr}/benchmark")
def get_benchmark(orgnr: str) -> dict:
    org = fetch_enhet_by_orgnr(orgnr)
    if not org:
        raise HTTPException(status_code=404, detail="Organisation not found")
    nace = org.get("naeringskode1") or ""
    benchmark = fetch_ssb_benchmark(nace)
    return {"orgnr": orgnr, "nace_code": nace, "benchmark": benchmark}


@router.get("/org/{orgnr}/struktur")
def get_company_struktur(orgnr: str) -> dict:
    """Return parent company and sub-units from BRREG (open, no auth)."""
    return {"orgnr": orgnr, **fetch_company_struktur(orgnr)}


@router.get("/norgesbank/rate/{currency}")
def get_norgesbank_rate(currency: str) -> dict:
    """Return current NOK exchange rate for the given currency (Norges Bank open API)."""
    rate = fetch_norgesbank_rate(currency.upper())
    return {
        "currency": currency.upper(),
        "nok_rate": rate,
        "source": "Norges Bank Data API (data.norges-bank.no)",
    }
