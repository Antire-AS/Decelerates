import logging
import os

import requests
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.dependencies import get_db
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


def _has_mp4_faststart(data: bytes):
    """Return True if moov box precedes mdat in the first chunk, False if not, None if inconclusive."""
    pos = 0
    while pos + 8 <= len(data):
        size = int.from_bytes(data[pos:pos + 4], "big")
        box_type = data[pos + 4:pos + 8].decode("ascii", errors="replace")
        if box_type == "moov":
            return True
        if box_type == "mdat":
            return False
        if size < 8 or pos + size > len(data):
            break
        pos += size
    return None


@router.get("/debug/status")
def debug_status() -> dict:
    """Diagnostic endpoint — returns blob storage health, DB state, and video moov-atom status."""
    from api.services.blob_storage import BlobStorageService
    from api.db import engine
    from sqlalchemy import text

    # --- Blob storage ---
    azure_client_id = os.getenv("AZURE_CLIENT_ID", "")
    azure_blob_endpoint = os.getenv("AZURE_BLOB_ENDPOINT", "")
    svc = BlobStorageService()
    blob_error = None
    blob_count = None
    blob_sample = []
    try:
        blobs = svc.list_blobs("transksrt")
        blob_count = len(blobs)
        blob_sample = blobs[:5]
    except Exception as exc:
        blob_error = str(exc)

    # --- DB migration state ---
    alembic_version = None
    alembic_error = None
    tables = []
    try:
        with engine.connect() as conn:
            alembic_version = conn.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            ).scalar()
            rows = conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public' ORDER BY table_name"
                )
            ).fetchall()
            tables = [r[0] for r in rows]
            # Check if tags column exists
            tags_col = conn.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                    "WHERE table_name='insurance_documents' AND column_name='tags')"
                )
            ).scalar()
    except Exception as exc:
        alembic_error = str(exc)
        tags_col = None

    # --- Video moov-atom check ---
    video_info = {}
    sas_url_works = None
    if svc._client:
        try:
            mp4_blobs = [b for b in svc.list_blobs("transksrt") if b.endswith(".mp4")]
            for mp4 in mp4_blobs:
                try:
                    chunks = svc.stream_range("transksrt", mp4, offset=0, length=256)
                    header = b"".join(chunks) if chunks else b""
                    sas_url = svc.generate_sas_url("transksrt", mp4, hours=1)
                    if sas_url_works is None:
                        sas_url_works = sas_url is not None
                    video_info[mp4] = {
                        "size_mb": round((svc.get_blob_size("transksrt", mp4) or 0) / 1e6),
                        "faststart": _has_mp4_faststart(header),
                        "sas_url_generated": sas_url is not None,
                    }
                except Exception as exc:
                    video_info[mp4] = {"error": str(exc)}
        except Exception:
            pass

    return {
        "azure_client_id_set": bool(azure_client_id),
        "azure_client_id_prefix": azure_client_id[:8] + "..." if azure_client_id else None,
        "azure_blob_endpoint_set": bool(azure_blob_endpoint),
        "blob_client_init": svc._client is not None,
        "blob_count": blob_count,
        "blob_sample": blob_sample,
        "blob_error": blob_error,
        "sas_url_works": sas_url_works,
        "video_info": video_info,
        "alembic_version": alembic_version,
        "alembic_error": alembic_error,
        "tags_column_exists": tags_col,
        "public_tables": tables,
    }


# ── Admin: reset + demo seed ───────────────────────────────────────────────

_log = logging.getLogger(__name__)

_DEMO_ORGNRS = [
    "984851006",   # DNB Bank ASA
    "995568217",   # Gjensidige Forsikring ASA
    "923609016",   # Equinor ASA
    "979981344",   # Søderberg & Partners Norge AS
    "943753709",   # Kongsberg Gruppen ASA
    "982463718",   # Telenor ASA
    "986228608",   # Yara International ASA
    "989795848",   # Aker BP ASA
]


@router.delete("/admin/reset")
def admin_reset(db: Session = Depends(get_db)) -> dict:
    """Delete all company data and portfolios — full clean slate."""
    from sqlalchemy import text
    tables = [
        "portfolio_companies", "portfolios",
        "company_chunks", "company_history", "company_pdf_sources",
        "company_notes", "companies",
    ]
    deleted = {}
    for table in tables:
        result = db.execute(text(f"DELETE FROM {table}"))
        deleted[table] = result.rowcount
    db.commit()
    return {"reset": True, "deleted_rows": deleted}


@router.post("/admin/demo")
def admin_demo(db: Session = Depends(get_db)) -> dict:
    """Seed demo portfolio with 8 major Norwegian companies and trigger PDF extraction."""
    from datetime import datetime, timezone
    from api.db import Portfolio, PortfolioCompany, SessionLocal
    from api.services.company import fetch_org_profile
    from api.services.pdf_extract import _auto_extract_pdf_sources
    from api.services.external_apis import fetch_enhet_by_orgnr
    from concurrent.futures import ThreadPoolExecutor

    # Create or reuse "Demo Portefølje"
    portfolio = db.query(Portfolio).filter(Portfolio.name == "Demo Portefølje").first()
    if not portfolio:
        portfolio = Portfolio(
            name="Demo Portefølje",
            description="Norges største selskaper — klar for demo",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        db.add(portfolio)
        db.commit()
        db.refresh(portfolio)

    # Fetch BRREG profiles + add to portfolio
    fetched, skipped = 0, 0
    existing = {
        pc.orgnr for pc in
        db.query(PortfolioCompany).filter(PortfolioCompany.portfolio_id == portfolio.id).all()
    }
    for orgnr in _DEMO_ORGNRS:
        if orgnr not in existing:
            db.add(PortfolioCompany(
                portfolio_id=portfolio.id,
                orgnr=orgnr,
                added_at=datetime.now(timezone.utc).isoformat(),
            ))
        try:
            fetch_org_profile(orgnr, db)
            fetched += 1
        except Exception as exc:
            _log.warning("Demo seed: failed for %s — %s", orgnr, exc)
            skipped += 1
    db.commit()

    # Trigger background PDF extraction for all demo companies
    def _run(orgnr: str) -> None:
        try:
            org = fetch_enhet_by_orgnr(orgnr) or {}
            _auto_extract_pdf_sources(orgnr, org, db_factory=SessionLocal)
        except Exception as exc:
            _log.warning("Demo PDF extraction: %s — %s", orgnr, exc)

    executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="demo_pdf")
    for orgnr in _DEMO_ORGNRS:
        executor.submit(_run, orgnr)
    executor.shutdown(wait=False)

    return {
        "portfolio_id": portfolio.id,
        "portfolio_name": portfolio.name,
        "companies": len(_DEMO_ORGNRS),
        "fetched": fetched,
        "skipped": skipped,
        "pdf_extraction": "started in background",
    }
