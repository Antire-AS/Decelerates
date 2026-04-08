from typing import Optional

import requests
from fastapi import APIRouter, Query, HTTPException, Depends, Request
from sqlalchemy.orm import Session

from api.services import fetch_enhetsregisteret, fetch_finanstilsynet_licenses, fetch_org_profile, list_companies as _list_companies
from api.services.insurance_needs import estimate_insurance_needs, build_insurance_narrative
from api.services.audit import log_audit
from api.services.job_queue_service import JobQueueService
from api.auth import get_optional_user, CurrentUser
from api.dependencies import get_db
from api.limiter import limiter
from api.schemas import LicensesOut, PeerBenchmarkOut

router = APIRouter()


@router.get("/ping")
def ping() -> dict:
    return {"status": "ok"}


@router.get("/search")
def search_orgs(
    name: str = Query(..., min_length=2),
    kommunenummer: Optional[str] = None,
    size: int = Query(20, ge=1, le=100),
) -> list:
    try:
        return fetch_enhetsregisteret(name=name, kommunenummer=kommunenummer, size=size)
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/org/{orgnr}")
@limiter.limit("10/minute")
def get_org_profile(
    request: Request,
    orgnr: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_optional_user),
):
    try:
        result = fetch_org_profile(orgnr, db)
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if result is None:
        raise HTTPException(status_code=404, detail="Organisation not found")

    org = (result or {}).get("org")
    log_audit(db, "view_company", orgnr=orgnr, actor_email=user.email if user else None,
              detail={"navn": (org or {}).get("navn")})
    JobQueueService(db).enqueue("pdf_extract", {"orgnr": orgnr, "org": org})

    return result


@router.get("/org/{orgnr}/licenses", response_model=LicensesOut)
def get_org_licenses(orgnr: str) -> dict:
    try:
        licenses = fetch_finanstilsynet_licenses(orgnr)
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {"orgnr": orgnr, "licenses": licenses}


@router.get("/companies")
def list_companies(
    limit: int = Query(50, ge=1, le=500),
    kommune: Optional[str] = None,
    nace_section: Optional[str] = None,
    min_revenue: Optional[float] = None,
    max_revenue: Optional[float] = None,
    min_risk: Optional[int] = None,
    max_risk: Optional[int] = None,
    min_employees: Optional[int] = None,
    sort_by: str = Query("revenue", pattern="^(revenue|risk_score|navn|regnskapsår)$"),
    db: Session = Depends(get_db),
) -> list:
    return _list_companies(
        limit, kommune, db,
        nace_section=nace_section,
        min_revenue=min_revenue,
        max_revenue=max_revenue,
        min_risk=min_risk,
        max_risk=max_risk,
        min_employees=min_employees,
        sort_by=sort_by,
    )


@router.get("/org/{orgnr}/insurance-needs")
def get_insurance_needs(orgnr: str, db: Session = Depends(get_db)) -> dict:
    """Return prioritised insurance needs estimate for a company."""
    from api.db import Company, CompanyHistory
    from api.services import fetch_enhet_by_orgnr

    db_obj = db.query(Company).filter(Company.orgnr == orgnr).first()
    if db_obj:
        org = {
            "orgnr": db_obj.orgnr,
            "navn": db_obj.navn,
            "naeringskode1": db_obj.naeringskode1,
            "organisasjonsform_kode": db_obj.organisasjonsform_kode,
            "antall_ansatte": db_obj.antall_ansatte,
            "sum_driftsinntekter": db_obj.sum_driftsinntekter,
            "sum_eiendeler": db_obj.sum_eiendeler,
            "sum_egenkapital": db_obj.sum_egenkapital,
        }
    else:
        # Company not yet saved to DB — fetch live from BRREG
        brreg = fetch_enhet_by_orgnr(orgnr) or {}
        if not brreg:
            raise HTTPException(status_code=404, detail="Organisation not found in BRREG")
        org = {
            "orgnr": orgnr,
            "navn": brreg.get("navn"),
            "naeringskode1": (brreg.get("naeringskode1") or {}).get("kode"),
            "organisasjonsform_kode": (brreg.get("organisasjonsform") or {}).get("kode"),
            "antall_ansatte": brreg.get("antallAnsatte"),
            "sum_driftsinntekter": None,
            "sum_eiendeler": None,
            "sum_egenkapital": None,
        }

    latest = (
        db.query(CompanyHistory)
        .filter(CompanyHistory.orgnr == orgnr)
        .order_by(CompanyHistory.year.desc())
        .first()
    ) if db_obj else None

    regn = {}
    if latest:
        regn = {
            "sum_driftsinntekter": latest.revenue,
            "sum_eiendeler": latest.total_assets,
            "antall_ansatte": latest.antall_ansatte,
            "lonnskostnad": (latest.raw or {}).get("lonnskostnad"),
        }

    needs = estimate_insurance_needs(org, regn)
    narrative = build_insurance_narrative(org, regn, needs)
    return {"orgnr": orgnr, "needs": needs, "narrative": narrative}


@router.get("/org/{orgnr}/peer-benchmark", response_model=PeerBenchmarkOut)
def get_peer_benchmark(orgnr: str, db: Session = Depends(get_db)) -> dict:
    """Compare a company's key ratios against peer companies in the same NACE section."""
    from api.db import Company
    from api.constants import _NACE_SECTION_MAP, NACE_BENCHMARKS
    import statistics

    db_obj = db.query(Company).filter(Company.orgnr == orgnr).first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Company not in database")

    nace = db_obj.naeringskode1 or ""
    section = ""
    try:
        code = int(str(nace).split(".")[0])
        for rng, s in _NACE_SECTION_MAP:
            if code in rng:
                section = s
                break
    except (ValueError, AttributeError):
        pass

    peers = (
        db.query(Company)
        .filter(Company.orgnr != orgnr, Company.naeringskode1.like(f"{nace[:2]}%"))
        .filter(Company.sum_driftsinntekter.isnot(None))
        .all()
    ) if len(nace) >= 2 else []

    def _pct(val, values):
        if val is None or not values:
            return None
        below = sum(1 for v in values if v < val)
        return round(below / len(values) * 100)

    if len(peers) >= 3:
        peer_revenues = [p.sum_driftsinntekter for p in peers if p.sum_driftsinntekter]
        peer_eq = [p.equity_ratio for p in peers if p.equity_ratio is not None]
        peer_risk = [p.risk_score for p in peers if p.risk_score is not None]
        metrics = {
            "equity_ratio": {
                "company": db_obj.equity_ratio,
                "peer_avg": round(statistics.mean(peer_eq), 3) if peer_eq else None,
                "percentile": _pct(db_obj.equity_ratio, peer_eq),
            },
            "revenue": {
                "company": db_obj.sum_driftsinntekter,
                "peer_avg": round(statistics.mean(peer_revenues)) if peer_revenues else None,
                "percentile": _pct(db_obj.sum_driftsinntekter, peer_revenues),
            },
            "risk_score": {
                "company": db_obj.risk_score,
                "peer_avg": round(statistics.mean(peer_risk), 1) if peer_risk else None,
                "percentile": _pct(db_obj.risk_score, peer_risk),
            },
        }
        source = "db_peers"
    else:
        bench = NACE_BENCHMARKS.get(section, {})
        eq_mid = (bench.get("eq_ratio_min", 0) + bench.get("eq_ratio_max", 0)) / 2 if bench else None
        metrics = {
            "equity_ratio": {
                "company": db_obj.equity_ratio,
                "peer_avg": round(eq_mid, 3) if eq_mid else None,
                "percentile": None,
            },
            "revenue": {"company": db_obj.sum_driftsinntekter, "peer_avg": None, "percentile": None},
            "risk_score": {"company": db_obj.risk_score, "peer_avg": None, "percentile": None},
        }
        source = "ssb_ranges"

    return {
        "orgnr": orgnr,
        "nace_section": section,
        "peer_count": len(peers),
        "metrics": metrics,
        "source": source,
    }


@router.get("/org-by-name")
def get_org_by_name(
    request: Request,
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
    return get_org_profile(request=request, orgnr=orgnr, db=db)
