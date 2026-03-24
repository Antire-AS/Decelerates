"""Client-token endpoints — generate and resolve read-only shareable profile links."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from datetime import datetime, timezone

from api.auth import CurrentUser, get_current_user, get_optional_user
from api.db import ClientToken, Company
from api.dependencies import get_db
from api.services import fetch_org_profile
from api.services.audit import log_audit
from api.services.client_token_service import (
    _TOKEN_TTL_DAYS,
    create_token,
    list_active_tokens,
)

router = APIRouter()


@router.post("/org/{orgnr}/client-token")
def create_client_token(
    orgnr: str,
    label: str = "",
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Generate a 30-day read-only token for sharing a company profile with a client."""
    if not db.query(Company).filter(Company.orgnr == orgnr).first():
        raise HTTPException(status_code=404, detail="Company not in database")
    row = create_token(orgnr, label or None, db)
    log_audit(db, "create_client_token", orgnr=orgnr, actor_email=user.email,
              detail={"label": label or None})
    return {"token": row.token, "orgnr": orgnr, "expires_days": _TOKEN_TTL_DAYS}


@router.get("/client/{token}")
def get_client_profile(
    token: str,
    db: Session = Depends(get_db),
    user: Optional[CurrentUser] = Depends(get_optional_user),
) -> dict:
    """Resolve a client token and return a read-only company profile snapshot."""
    row = db.query(ClientToken).filter(ClientToken.token == token).first()
    if not row:
        raise HTTPException(status_code=404, detail="Token not found")
    if row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Token expired")
    profile = fetch_org_profile(row.orgnr, db)
    if not profile:
        raise HTTPException(status_code=404, detail="Company not found")
    org = profile.get("org") or {}
    risk = profile.get("risk") or {}
    actor = user.email if user else "client"
    log_audit(db, "view_client_profile", orgnr=row.orgnr, actor_email=actor,
              detail={"token_label": row.label})
    return {
        "orgnr": row.orgnr,
        "navn": org.get("navn"),
        "kommune": org.get("kommune"),
        "naeringskode1_beskrivelse": org.get("naeringskode1_beskrivelse"),
        "antall_ansatte": org.get("antall_ansatte"),
        "sum_driftsinntekter": org.get("sum_driftsinntekter"),
        "risk_score": risk.get("score"),
        "risk_reasons": risk.get("reasons", []),
        "regnskap": profile.get("regnskap") or {},
        "expires_at": row.expires_at.isoformat(),
    }


@router.get("/org/{orgnr}/client-tokens")
def list_client_tokens(orgnr: str, db: Session = Depends(get_db)) -> list:
    """List all active tokens for a company."""
    rows = list_active_tokens(orgnr, db)
    return [
        {"token": r.token, "label": r.label, "expires_at": r.expires_at.isoformat(),
         "created_at": r.created_at.isoformat()}
        for r in rows
    ]
