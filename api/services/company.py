"""Company service — seeding, upsert, org profile, narratives, synthetic financials."""

import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import requests
from sqlalchemy.orm import Session

from api.constants import PDF_SEED_DATA
from api.db import Company, CompanyHistory, CompanyPdfSource
from api.risk import build_risk_summary, compute_altman_z_score, derive_simple_risk
from api.services.external_apis import (
    fetch_regnskap_keyfigures,
    pep_screen_name,
)
from api.services.llm import _fmt_nok, _llm_answer_raw
import logging

logger = logging.getLogger(__name__)


def _seed_pdf_sources(db: Session) -> None:
    """Upsert hardcoded PDF sources into company_pdf_sources table on startup."""
    for orgnr, entries in PDF_SEED_DATA.items():
        for entry in entries:
            existing = (
                db.query(CompanyPdfSource)
                .filter(
                    CompanyPdfSource.orgnr == orgnr,
                    CompanyPdfSource.year == entry["year"],
                )
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


def _financials_db_fallback(orgnr: str, db: Session) -> Dict[str, Any]:
    """Return financial key figures from the most recent company_history row, or {}.

    Pure DB lookup, no network. Caller is responsible for holding a live session.
    """
    recent_hist = (
        db.query(CompanyHistory)
        .filter(CompanyHistory.orgnr == orgnr)
        .order_by(CompanyHistory.year.desc())
        .first()
    )
    if not recent_hist:
        return {}
    raw_fields = dict(recent_hist.raw) if recent_hist.raw else {}
    # Derive sum_gjeld from short+long term debt if not already in raw
    short_debt = recent_hist.short_term_debt or 0
    long_debt = recent_hist.long_term_debt or 0
    gjeld_fallback = (short_debt + long_debt) or raw_fields.get("sum_gjeld")
    return {
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


def _fetch_financials_with_fallback(orgnr: str, db: Session) -> Dict[str, Any]:
    """Fetch financials from BRREG; fall back to most recent PDF history row if empty.

    Public helper (module-level callers rely on this signature). Internally
    fetch_org_profile uses the parallel variant below.
    """
    try:
        regn = fetch_regnskap_keyfigures(orgnr)
    except requests.HTTPError:
        regn = {}
    return regn or _financials_db_fallback(orgnr, db)


def _safe_fetch_regn(orgnr: str) -> Dict[str, Any]:
    """HTTP-only regnskap fetch. Thread-safe (no DB access). Returns {} on HTTPError."""
    try:
        return fetch_regnskap_keyfigures(orgnr)
    except requests.HTTPError:
        return {}


def _safe_pep_screen(name: str) -> Optional[Dict[str, Any]]:
    """PEP screen with HTTPError swallow. Thread-safe."""
    if not name:
        return None
    try:
        return pep_screen_name(name)
    except requests.HTTPError:
        return None


def fetch_org_profile(orgnr: str, db: Session) -> Optional[Dict[str, Any]]:
    """Fetch the full org profile. Parallelises the three external HTTP calls
    (BRREG-enhet + BRREG-regnskap + OpenSanctions-PEP) via ThreadPoolExecutor
    so cold requests drop from ~sum → ~max of the individual 10 s timeouts.
    PEP depends on enhet's company name, so fires as soon as enhet returns.
    DB access stays on the caller thread (sessions aren't thread-safe).
    ``cached_fetch_enhet`` means the 4 utility endpoints fired in parallel
    from the company-profile page hit a 5-min TTL cache rather than BRREG.
    """
    from api.services.caching import cached_fetch_enhet

    with ThreadPoolExecutor(max_workers=3) as ex:
        enhet_future = ex.submit(cached_fetch_enhet, orgnr)
        regn_future = ex.submit(_safe_fetch_regn, orgnr)

        org = enhet_future.result()
        if not org:
            regn_future.result()  # drain so the thread exits cleanly
            return None

        pep_future = ex.submit(_safe_pep_screen, org.get("navn", ""))
        regn_http = regn_future.result()
        pep = pep_future.result()

    regn = regn_http or _financials_db_fallback(orgnr, db)
    risk = derive_simple_risk(org, regn, pep) if regn else None
    _upsert_company(db, orgnr, org, regn, risk, pep)

    return {
        "org": org,
        "regnskap": regn or None,
        "risk": risk,
        "pep": pep,
        "risk_summary": build_risk_summary(org, regn or {}, risk or {}, pep or {}),
    }


def _resolve_nace_section(nace: str) -> str:
    """Map a full NACE code like '62.010' to its A-S section letter."""
    from api.constants import _NACE_SECTION_MAP

    try:
        code = int(str(nace).split(".")[0])
    except (ValueError, AttributeError):
        return ""
    for rng, section in _NACE_SECTION_MAP:
        if code in rng:
            return section
    return ""


def _fetch_peer_companies(orgnr: str, nace: str, db: Session) -> List[Company]:
    if len(nace) < 2:
        return []
    return (
        db.query(Company)
        .filter(Company.orgnr != orgnr, Company.naeringskode1.like(f"{nace[:2]}%"))
        .filter(Company.sum_driftsinntekter.isnot(None))
        .all()
    )


def _percentile_of(val: Optional[float], values: List[float]) -> Optional[int]:
    if val is None or not values:
        return None
    below = sum(1 for v in values if v < val)
    return round(below / len(values) * 100)


def _db_peer_metrics(db_obj: Company, peers: List[Company]) -> Dict[str, Any]:
    import statistics

    peer_revenues = [p.sum_driftsinntekter for p in peers if p.sum_driftsinntekter]
    peer_eq = [p.equity_ratio for p in peers if p.equity_ratio is not None]
    peer_risk = [p.risk_score for p in peers if p.risk_score is not None]
    return {
        "equity_ratio": {
            "company": db_obj.equity_ratio,
            "peer_avg": round(statistics.mean(peer_eq), 3) if peer_eq else None,
            "percentile": _percentile_of(db_obj.equity_ratio, peer_eq),
        },
        "revenue": {
            "company": db_obj.sum_driftsinntekter,
            "peer_avg": round(statistics.mean(peer_revenues))
            if peer_revenues
            else None,
            "percentile": _percentile_of(db_obj.sum_driftsinntekter, peer_revenues),
        },
        "risk_score": {
            "company": db_obj.risk_score,
            "peer_avg": round(statistics.mean(peer_risk), 1) if peer_risk else None,
            "percentile": _percentile_of(db_obj.risk_score, peer_risk),
        },
    }


def _ssb_fallback_metrics(db_obj: Company, section: str) -> Dict[str, Any]:
    from api.constants import NACE_BENCHMARKS

    bench = NACE_BENCHMARKS.get(section, {})
    eq_mid = (
        (bench.get("eq_ratio_min", 0) + bench.get("eq_ratio_max", 0)) / 2
        if bench
        else None
    )
    return {
        "equity_ratio": {
            "company": db_obj.equity_ratio,
            "peer_avg": round(eq_mid, 3) if eq_mid else None,
            "percentile": None,
        },
        "revenue": {
            "company": db_obj.sum_driftsinntekter,
            "peer_avg": None,
            "percentile": None,
        },
        "risk_score": {
            "company": db_obj.risk_score,
            "peer_avg": None,
            "percentile": None,
        },
    }


def compute_peer_benchmark(orgnr: str, db: Session) -> Optional[Dict[str, Any]]:
    """Build a peer-comparison summary by NACE section.

    Returns the same shape the GET /org/{orgnr}/peer-benchmark router returns
    so UI + narrative prompt share a single source of truth. Returns None if
    the company row is missing — callers decide whether that's a 404 or a
    silent skip.
    """
    db_obj = db.query(Company).filter(Company.orgnr == orgnr).first()
    if not db_obj:
        return None
    nace = db_obj.naeringskode1 or ""
    section = _resolve_nace_section(nace)
    peers = _fetch_peer_companies(orgnr, nace, db)
    if len(peers) >= 3:
        metrics = _db_peer_metrics(db_obj, peers)
        source = "db_peers"
    else:
        metrics = _ssb_fallback_metrics(db_obj, section)
        source = "ssb_ranges"
    return {
        "orgnr": orgnr,
        "nace_section": section,
        "peer_count": len(peers),
        "metrics": metrics,
        "source": source,
    }


def _format_altman_block(regn: Dict[str, Any]) -> str:
    """Altman Z'' section — included only when enough financial fields are
    extracted to compute the four ratios. Banks/insurers hit the None branch
    because they lack the current/non-current split."""
    altman = compute_altman_z_score(regn)
    if altman is None:
        return ""
    c = altman["components"]
    return f"""
Altman Z'' distress model: {altman["z_score"]:.2f} ({altman["zone"]} zone)
  - Working capital / total assets (liquidity): {c["working_capital_ratio"]:.3f}
  - Retained earnings / total assets (history): {c["retained_earnings_ratio"]:.3f}
  - EBIT / total assets (profitability):        {c["ebit_ratio"]:.3f}
  - Equity / total liabilities (solvency):      {c["equity_to_liab_ratio"]:.3f}"""


def _format_peer_block(peer_summary: Optional[Dict[str, Any]]) -> str:
    """Peer benchmark delta — included when the caller supplies summary data
    from /peer-benchmark. Kept terse so the LLM weighs direction > precision."""
    if not peer_summary:
        return ""
    metrics = peer_summary.get("metrics") or {}
    eq = metrics.get("equity_ratio") or {}
    rev = metrics.get("revenue") or {}
    lines: List[str] = []
    if eq.get("company") is not None and eq.get("peer_avg") is not None:
        pct = eq.get("percentile")
        suffix = f" (P{pct})" if pct is not None else ""
        lines.append(
            f"  - Equity ratio: {eq['company'] * 100:.1f}% vs peer avg {eq['peer_avg'] * 100:.1f}%{suffix}"
        )
    if rev.get("company") is not None and rev.get("peer_avg") is not None:
        pct = rev.get("percentile")
        suffix = f" (P{pct})" if pct is not None else ""
        lines.append(
            f"  - Revenue: {_fmt_nok(rev['company'])} vs peer avg {_fmt_nok(rev['peer_avg'])}{suffix}"
        )
    if not lines:
        return ""
    section = peer_summary.get("nace_section") or "?"
    count = peer_summary.get("peer_count") or 0
    header = f"\nPeer comparison (NACE {section}, {count} peers):"
    return header + "\n" + "\n".join(lines)


def _build_narrative_prompt(
    org: Dict[str, Any],
    regn: Dict[str, Any],
    risk: Optional[Dict[str, Any]],
    pep: Optional[Dict[str, Any]],
    members: List[Dict[str, Any]],
    lang: str = "no",
    peer_summary: Optional[Dict[str, Any]] = None,
) -> str:
    """Build the LLM prompt for a risk narrative."""
    eq_pct = (
        f"{risk['equity_ratio'] * 100:.1f}%"
        if risk and risk.get("equity_ratio") is not None
        else "unknown"
    )
    board_str = (
        ", ".join(f"{m['name']} ({m['role']})" for m in members[:6] if m.get("name"))
        or "Not available"
    )
    flags_str = ", ".join(risk.get("reasons") or []) if risk else "none"
    synthetic_note = (
        " (NOTE: financials are AI-estimated, no public data available)"
        if regn.get("synthetic")
        else ""
    )
    lang_instruction = "Write in English." if lang == "en" else "Svar på norsk."
    altman_block = _format_altman_block(regn)
    peer_block = _format_peer_block(peer_summary)
    return f"""Write a concise 3-paragraph risk assessment for an insurance underwriter considering this Norwegian company as a client.{synthetic_note} {lang_instruction}

Company: {org.get("navn")} ({org.get("organisasjonsform")}, {org.get("organisasjonsform_kode")})
Industry: {org.get("naeringskode1")} – {org.get("naeringskode1_beskrivelse")}
Location: {org.get("kommune")}, Norway
Board / key roles: {board_str}

Financials ({regn.get("regnskapsår", "estimated")}):
- Revenue: {_fmt_nok(regn.get("sum_driftsinntekter"))}
- Net result: {_fmt_nok(regn.get("aarsresultat"))}
- Total equity: {_fmt_nok(regn.get("sum_egenkapital"))}
- Total assets: {_fmt_nok(regn.get("sum_eiendeler"))}
- Equity ratio: {eq_pct}
- Employees: {regn.get("antall_ansatte", "N/A")}
{altman_block}
{peer_block}

Risk score: {risk.get("score", "N/A") if risk else "N/A"} | Flags: {flags_str}
PEP/sanctions hits: {pep.get("hit_count", 0) if pep else 0}

Paragraph 1 – Business profile: Summarise what this company does, its scale, and financial position.
Paragraph 2 – Underwriting concerns: Identify the main risk factors. If Altman Z'' is in the grey or distress zone, cite the specific component(s) (liquidity vs solvency vs profitability) that are dragging the score down. If peer comparison shows the company in the bottom quartile on equity or revenue, flag it.
Paragraph 3 – Recommendation: Overall risk stance and 2–3 specific questions to ask before binding coverage.

Be specific, professional, and concise. Do not make up data beyond what is provided."""


def _generate_risk_narrative(
    org: Dict[str, Any],
    regn: Dict[str, Any],
    risk: Optional[Dict[str, Any]],
    pep: Optional[Dict[str, Any]],
    members: List[Dict[str, Any]],
    lang: str = "no",
    peer_summary: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    prompt = _build_narrative_prompt(
        org, regn, risk, pep, members, lang, peer_summary=peer_summary
    )
    return _llm_answer_raw(prompt)


def list_companies(
    limit: int,
    kommune: Optional[str],
    db: Session,
    nace_section: Optional[str] = None,
    min_revenue: Optional[float] = None,
    max_revenue: Optional[float] = None,
    min_risk: Optional[int] = None,
    max_risk: Optional[int] = None,
    min_employees: Optional[int] = None,
    sort_by: str = "revenue",
) -> List[Dict[str, Any]]:
    from api.constants import _NACE_SECTION_MAP

    q = db.query(Company).filter(Company.deleted_at.is_(None))
    if kommune:
        q = q.filter(Company.kommune == kommune)
    if nace_section:
        # Collect all NACE codes for the section
        codes = [
            str(c)
            for rng, s in _NACE_SECTION_MAP
            if s == nace_section.upper()
            for c in rng
        ]
        if codes:
            q = q.filter(
                Company.naeringskode1.in_(codes)
                | Company.naeringskode1.like(f"{nace_section.upper()}%")
            )
    if min_revenue is not None:
        q = q.filter(Company.sum_driftsinntekter >= min_revenue)
    if max_revenue is not None:
        q = q.filter(Company.sum_driftsinntekter <= max_revenue)
    if min_risk is not None:
        q = q.filter(Company.risk_score >= min_risk)
    if max_risk is not None:
        q = q.filter(Company.risk_score <= max_risk)
    if min_employees is not None:
        q = q.filter(Company.antall_ansatte >= min_employees)

    _SORT_MAP = {
        "revenue": Company.sum_driftsinntekter.desc().nulls_last(),
        "risk_score": Company.risk_score.desc().nulls_last(),
        "navn": Company.navn.asc(),
        "regnskapsår": Company.regnskapsår.desc().nulls_last(),
    }
    q = q.order_by(
        _SORT_MAP.get(sort_by, Company.sum_driftsinntekter.desc().nulls_last())
    )
    rows = q.limit(limit).all()
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
            "antall_ansatte": c.antall_ansatte,
            "risk_score": c.risk_score,
        }
        for c in rows
    ]


def _generate_synthetic_financials(org: Dict[str, Any]) -> Dict[str, Any]:
    """Estimate key financial figures for companies with no public Regnskapsregisteret data."""
    prompt = f"""Estimate realistic financial figures for a Norwegian company. Return ONLY a valid JSON object, no explanation.

Company:
- Legal form: {org.get("organisasjonsform")} ({org.get("organisasjonsform_kode")})
- Industry: {org.get("naeringskode1")} – {org.get("naeringskode1_beskrivelse")}
- Municipality: {org.get("kommune")}

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


# ── Service class wrapper ──────────────────────────────────────────────────────


class CompanyService:
    """Thin class wrapper around module-level company helpers."""

    def __init__(self, db) -> None:
        self.db = db

    def fetch_org_profile(self, orgnr: str):
        return fetch_org_profile(orgnr, self.db)

    def list_companies(self, limit: int = 50, kommune=None):
        return list_companies(limit, kommune, self.db)

    def seed_pdf_sources(self):
        _seed_pdf_sources(self.db)

    def get_property_metadata(self, orgnr: str) -> dict:
        """Return the JSONB blob (or empty dict) for a company's
        property fields — building year, fire alarm, etc."""
        from api.models.company import Company

        c = self.db.query(Company).filter(Company.orgnr == orgnr).first()
        if c is None:
            raise ValueError(f"Company {orgnr} not found")
        return dict(c.property_metadata or {})

    def update_property_metadata(self, orgnr: str, patch: dict) -> dict:
        """Merge `patch` into the JSONB blob; returns the new full state.
        A key with `None` value is removed."""
        from api.models.company import Company

        c = self.db.query(Company).filter(Company.orgnr == orgnr).first()
        if c is None:
            raise ValueError(f"Company {orgnr} not found")
        merged: dict = dict(c.property_metadata or {})
        for k, v in patch.items():
            if v is None:
                merged.pop(k, None)
            else:
                merged[k] = v
        c.property_metadata = merged
        self.db.commit()
        self.db.refresh(c)
        return merged
