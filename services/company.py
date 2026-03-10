"""Company service — seeding, upsert, org profile, narratives, synthetic financials."""
import json
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import requests
from sqlalchemy.orm import Session

from constants import PDF_SEED_DATA
from db import Company, CompanyHistory, CompanyPdfSource
from risk import derive_simple_risk, build_risk_summary
from services.external_apis import fetch_enhet_by_orgnr, fetch_regnskap_keyfigures, pep_screen_name
from services.llm import _fmt_nok, _llm_answer_raw


def _seed_pdf_sources(db: Session) -> None:
    """Upsert hardcoded PDF sources into company_pdf_sources table on startup."""
    for orgnr, entries in PDF_SEED_DATA.items():
        for entry in entries:
            existing = (
                db.query(CompanyPdfSource)
                .filter(CompanyPdfSource.orgnr == orgnr, CompanyPdfSource.year == entry["year"])
                .first()
            )
            if not existing:
                existing = CompanyPdfSource(
                    orgnr=orgnr,
                    year=entry["year"],
                    added_at=datetime.now(timezone.utc).isoformat(),
                )
                db.add(existing)
            existing.pdf_url = entry["pdf_url"]
            existing.label = entry.get("label", "")
    db.commit()


def _upsert_company(
    db: Session,
    orgnr: str,
    org: Dict[str, Any],
    regn: Dict[str, Any],
    risk: Optional[Dict[str, Any]],
    pep: Optional[Dict[str, Any]],
) -> None:
    db_obj = db.query(Company).filter(Company.orgnr == orgnr).first()
    if not db_obj:
        db_obj = Company(orgnr=orgnr)
        db.add(db_obj)

    db_obj.navn = org.get("navn")
    db_obj.organisasjonsform_kode = org.get("organisasjonsform_kode")
    db_obj.kommune = org.get("kommune")
    db_obj.land = org.get("land")
    db_obj.naeringskode1 = org.get("naeringskode1")
    db_obj.naeringskode1_beskrivelse = org.get("naeringskode1_beskrivelse")

    if regn:
        db_obj.regnskapsår = regn.get("regnskapsår")
        db_obj.sum_driftsinntekter = regn.get("sum_driftsinntekter")
        db_obj.sum_egenkapital = regn.get("sum_egenkapital")
        db_obj.sum_eiendeler = regn.get("sum_eiendeler")
        if risk:
            db_obj.equity_ratio = risk.get("equity_ratio")
            db_obj.risk_score = risk.get("score")
        db_obj.regnskap_raw = regn

    if pep:
        db_obj.pep_raw = pep

    db.commit()


def _fetch_financials_with_fallback(orgnr: str, db: Session) -> Dict[str, Any]:
    """Fetch financials from BRREG; fall back to most recent PDF history row if empty."""
    try:
        regn = fetch_regnskap_keyfigures(orgnr)
    except requests.HTTPError:
        regn = {}

    if not regn:
        recent_hist = (
            db.query(CompanyHistory)
            .filter(CompanyHistory.orgnr == orgnr)
            .order_by(CompanyHistory.year.desc())
            .first()
        )
        if recent_hist:
            raw_fields = dict(recent_hist.raw) if recent_hist.raw else {}
            # Derive sum_gjeld from short+long term debt if not already in raw
            short_debt = recent_hist.short_term_debt or 0
            long_debt = recent_hist.long_term_debt or 0
            gjeld_fallback = (short_debt + long_debt) or raw_fields.get("sum_gjeld")
            regn = {
                **raw_fields,
                "regnskapsår": recent_hist.year,
                "sum_driftsinntekter": recent_hist.revenue,
                "aarsresultat": recent_hist.net_result,
                "sum_egenkapital": recent_hist.equity,
                "sum_eiendeler": recent_hist.total_assets,
                "sum_gjeld": gjeld_fallback,
                "equity_ratio": recent_hist.equity_ratio,
                "antall_ansatte": recent_hist.antall_ansatte,
                "_source": "pdf_history",
            }
    return regn


def fetch_org_profile(orgnr: str, db: Session) -> Optional[Dict[str, Any]]:
    org = fetch_enhet_by_orgnr(orgnr)
    if not org:
        return None

    regn = _fetch_financials_with_fallback(orgnr, db)

    try:
        pep = pep_screen_name(org.get("navn", ""))
    except requests.HTTPError:
        pep = None

    risk = derive_simple_risk(org, regn, pep) if regn else None
    _upsert_company(db, orgnr, org, regn, risk, pep)

    return {
        "org": org,
        "regnskap": regn or None,
        "risk": risk,
        "pep": pep,
        "risk_summary": build_risk_summary(org, regn or {}, risk or {}, pep or {}),
    }


def _build_narrative_prompt(
    org: Dict[str, Any],
    regn: Dict[str, Any],
    risk: Optional[Dict[str, Any]],
    pep: Optional[Dict[str, Any]],
    members: List[Dict[str, Any]],
    lang: str = "no",
) -> str:
    """Build the LLM prompt for a risk narrative."""
    eq_pct = (
        f"{risk['equity_ratio']*100:.1f}%"
        if risk and risk.get("equity_ratio") is not None
        else "unknown"
    )
    board_str = ", ".join(
        f"{m['name']} ({m['role']})" for m in members[:6] if m.get("name")
    ) or "Not available"
    flags_str = ", ".join(risk.get("reasons") or []) if risk else "none"
    synthetic_note = " (NOTE: financials are AI-estimated, no public data available)" if regn.get("synthetic") else ""
    lang_instruction = "Write in English." if lang == "en" else "Svar på norsk."
    return f"""Write a concise 3-paragraph risk assessment for an insurance underwriter considering this Norwegian company as a client.{synthetic_note} {lang_instruction}

Company: {org.get('navn')} ({org.get('organisasjonsform')}, {org.get('organisasjonsform_kode')})
Industry: {org.get('naeringskode1')} – {org.get('naeringskode1_beskrivelse')}
Location: {org.get('kommune')}, Norway
Board / key roles: {board_str}

Financials ({regn.get('regnskapsår', 'estimated')}):
- Revenue: {_fmt_nok(regn.get('sum_driftsinntekter'))}
- Net result: {_fmt_nok(regn.get('aarsresultat'))}
- Total equity: {_fmt_nok(regn.get('sum_egenkapital'))}
- Total assets: {_fmt_nok(regn.get('sum_eiendeler'))}
- Equity ratio: {eq_pct}
- Employees: {regn.get('antall_ansatte', 'N/A')}

Risk score: {risk.get('score', 'N/A') if risk else 'N/A'} | Flags: {flags_str}
PEP/sanctions hits: {pep.get('hit_count', 0) if pep else 0}

Paragraph 1 – Business profile: Summarise what this company does, its scale, and financial position.
Paragraph 2 – Underwriting concerns: Identify the main risk factors (financial stability, governance quality, PEP exposure, industry risk).
Paragraph 3 – Recommendation: Overall risk stance and 2–3 specific questions to ask before binding coverage.

Be specific, professional, and concise. Do not make up data beyond what is provided."""


def _generate_risk_narrative(
    org: Dict[str, Any],
    regn: Dict[str, Any],
    risk: Optional[Dict[str, Any]],
    pep: Optional[Dict[str, Any]],
    members: List[Dict[str, Any]],
    lang: str = "no",
) -> Optional[str]:
    prompt = _build_narrative_prompt(org, regn, risk, pep, members, lang)
    return _llm_answer_raw(prompt)


def list_companies(limit: int, kommune: Optional[str], db: Session) -> List[Dict[str, Any]]:
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


def _generate_synthetic_financials(org: Dict[str, Any]) -> Dict[str, Any]:
    """Estimate key financial figures for companies with no public Regnskapsregisteret data."""
    prompt = f"""Estimate realistic financial figures for a Norwegian company. Return ONLY a valid JSON object, no explanation.

Company:
- Legal form: {org.get('organisasjonsform')} ({org.get('organisasjonsform_kode')})
- Industry: {org.get('naeringskode1')} – {org.get('naeringskode1_beskrivelse')}
- Municipality: {org.get('kommune')}

Use typical median values for this type of Norwegian company. All values in NOK as integers.
Return exactly this JSON structure:
{{"sum_driftsinntekter": 0, "aarsresultat": 0, "sum_egenkapital": 0, "sum_eiendeler": 0, "sum_gjeld": 0, "antall_ansatte": 0}}"""

    raw = _llm_answer_raw(prompt)
    if not raw:
        return {}

    match = re.search(r"\{[^{}]+\}", raw, re.DOTALL)
    if not match:
        return {}

    try:
        data = json.loads(match.group())
        equity = data.get("sum_egenkapital")
        assets = data.get("sum_eiendeler")
        equity_ratio = (equity / assets) if (equity and assets) else None
        return {
            "regnskapsår": None,
            "sum_driftsinntekter": data.get("sum_driftsinntekter"),
            "aarsresultat": data.get("aarsresultat"),
            "sum_egenkapital": equity,
            "sum_eiendeler": assets,
            "sum_gjeld": data.get("sum_gjeld"),
            "antall_ansatte": data.get("antall_ansatte"),
            "equity_ratio": equity_ratio,
            "synthetic": True,
        }
    except (json.JSONDecodeError, TypeError, ZeroDivisionError):
        return {}
