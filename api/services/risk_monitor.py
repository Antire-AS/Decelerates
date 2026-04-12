"""Portfolio risk monitor agent — weekly refresh of BRREG data + risk re-scoring.

Re-fetches financials from BRREG for all companies in all portfolios,
re-calculates risk scores, and creates notifications when a company's
risk changes by more than 2 points.

Called via POST /admin/refresh-portfolio-risk (wired to a weekly GitHub
Actions cron). Designed for batch operation with rate-limiting (500ms
delay between BRREG requests) to avoid hammering the government API.

This is PR 5 of the AI Agent Acceleration Roadmap.
"""
import logging
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from api.db import Company, NotificationKind, PortfolioCompany

_log = logging.getLogger(__name__)
_BRREG_DELAY_S = 0.5  # polite pause between BRREG requests
_RISK_CHANGE_THRESHOLD = 2  # notify when score changes by > this


def _fetch_brreg_data(orgnr: str) -> tuple[dict, dict] | None:
    """Fetch fresh org + financial data from BRREG. Returns None on failure."""
    from api.services.brreg_client import fetch_enhet_by_orgnr, fetch_regnskap_keyfigures
    try:
        return fetch_enhet_by_orgnr(orgnr) or {}, fetch_regnskap_keyfigures(orgnr) or {}
    except Exception as exc:
        _log.warning("Risk monitor: BRREG fetch failed for %s: %s", orgnr, exc)
        return None


def _update_company_fields(company: Company, regn: dict, new_score: int, eq_ratio: float | None) -> None:
    """Apply fresh BRREG data to the Company row."""
    company.risk_score = new_score
    company.equity_ratio = eq_ratio
    if regn.get("sum_driftsinntekter"):
        company.sum_driftsinntekter = regn["sum_driftsinntekter"]
    if regn.get("sum_egenkapital"):
        company.sum_egenkapital = regn["sum_egenkapital"]
    if regn.get("sum_eiendeler"):
        company.sum_eiendeler = regn["sum_eiendeler"]
    company.last_refreshed_at = datetime.now(timezone.utc)


def _refresh_company(orgnr: str, db: Session) -> dict[str, Any] | None:
    """Re-fetch BRREG data and re-score one company. Returns change dict or None."""
    from api.risk import derive_simple_risk
    company = db.query(Company).filter(Company.orgnr == orgnr).first()
    if not company:
        return None
    old_score = company.risk_score
    result = _fetch_brreg_data(orgnr)
    if result is None:
        return None
    org, regn = result
    risk = derive_simple_risk(org, regn)
    new_score = risk.get("score", old_score)
    _update_company_fields(company, regn, new_score, risk.get("equity_ratio"))
    change = abs((new_score or 0) - (old_score or 0))
    if change > _RISK_CHANGE_THRESHOLD:
        return {"orgnr": orgnr, "navn": company.navn or orgnr,
                "old_score": old_score, "new_score": new_score, "change": change}
    return None


def _notify_risk_changes(risk_changes: list[dict], firm_id: int, db: Session) -> None:
    """Create in-app notifications for significant risk score changes."""
    from api.services.notification_inbox_service import create_notification_for_users_safe
    for ch in risk_changes:
        direction = "økt" if (ch["new_score"] or 0) > (ch["old_score"] or 0) else "redusert"
        create_notification_for_users_safe(
            db, firm_id=firm_id, kind=NotificationKind.coverage_gap,
            title=f"Risikoendring: {ch['navn']}",
            message=f"Risikoscore {direction} fra {ch['old_score']} til {ch['new_score']}",
            link=f"/search/{ch['orgnr']}", orgnr=ch["orgnr"],
        )


def refresh_all_portfolios(firm_id: int, db: Session) -> dict[str, Any]:
    """Refresh BRREG data for all portfolio companies. Returns summary."""
    orgnrs = list({pc.orgnr for pc in db.query(PortfolioCompany.orgnr).distinct().all()})
    refreshed = 0
    risk_changes: list[dict] = []
    for orgnr in orgnrs:
        change = _refresh_company(orgnr, db)
        refreshed += 1
        if change:
            risk_changes.append(change)
        time.sleep(_BRREG_DELAY_S)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    _notify_risk_changes(risk_changes, firm_id, db)
    return {"companies_refreshed": refreshed, "risk_changes": risk_changes, "total_changes": len(risk_changes)}
