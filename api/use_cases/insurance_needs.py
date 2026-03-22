"""Rule-based insurance needs estimator for Norwegian companies.

Produces a prioritised list of insurance types with estimated coverage amounts
plus a short LLM narrative summarising the company's risk profile.
No DB access — pure function over company data dicts.
"""
from __future__ import annotations

from typing import Any

from api.constants import _NACE_SECTION_MAP


# ── NACE section helper ───────────────────────────────────────────────────────

def _nace_section(naeringskode: str | None) -> str:
    """Return the single-letter NACE section (A–S) for a numeric NACE code."""
    if not naeringskode:
        return ""
    try:
        code = int(str(naeringskode).split(".")[0])
    except (ValueError, AttributeError):
        return ""
    for code_range, section in _NACE_SECTION_MAP:
        if code in code_range:
            return section
    return ""


# ── Coverage formula helpers ──────────────────────────────────────────────────

def _mnok(value: float) -> int:
    """Round to nearest 100k NOK and return as integer NOK."""
    return int(round(value / 100_000) * 100_000)


# ── Rule engine ───────────────────────────────────────────────────────────────

def estimate_insurance_needs(org: dict[str, Any], regn: dict[str, Any]) -> list[dict]:
    """Return a list of insurance need dicts, sorted by priority.

    Each dict: {type, priority, estimated_coverage_nok, reason}
    Priority values: "Kritisk" > "Anbefalt" > "Vurder"
    """
    revenue: float = regn.get("sum_driftsinntekter") or org.get("sum_driftsinntekter") or 0
    total_assets: float = regn.get("sum_eiendeler") or org.get("sum_eiendeler") or 0
    employees: int = int(regn.get("antall_ansatte") or org.get("antall_ansatte") or 0)
    lonnskostnad: float = regn.get("lonnskostnad") or 0
    org_form: str = (org.get("organisasjonsform_kode") or "").upper()
    nace: str = org.get("naeringskode1") or org.get("naeringskode") or ""
    section = _nace_section(nace)

    needs: list[dict] = []

    # 1. Yrkesskadeforsikring — mandatory for any employer
    if employees > 0:
        if lonnskostnad > 0:
            coverage = _mnok(lonnskostnad * 15)
        else:
            coverage = _mnok(employees * 600_000 * 15)
        needs.append({
            "type": "Yrkesskadeforsikring",
            "priority": "Kritisk",
            "estimated_coverage_nok": max(coverage, 5_000_000),
            "reason": f"Lovpålagt for alle arbeidsgivere (AML § 16-7). {employees} ansatte.",
        })

    # 2. Ansvarsforsikring — always recommended
    coverage = _mnok(max(5_000_000, revenue * 0.5))
    needs.append({
        "type": "Ansvarsforsikring",
        "priority": "Kritisk",
        "estimated_coverage_nok": coverage,
        "reason": "Grunnleggende erstatningsrettslig dekning. Minimum 5 MNOK.",
    })

    # 3. Eiendomsforsikring — if significant assets
    if total_assets > 5_000_000:
        coverage = _mnok(total_assets * 0.8)
        needs.append({
            "type": "Eiendomsforsikring",
            "priority": "Anbefalt",
            "estimated_coverage_nok": coverage,
            "reason": f"Gjenverdi av eiendeler (80 % av sum eiendeler {total_assets/1e6:.0f} MNOK).",
        })

    # 4. Styreansvarsforsikring (D&O) — AS/ASA
    if org_form in ("AS", "ASA"):
        coverage = _mnok(max(2_000_000, revenue * 0.1))
        needs.append({
            "type": "Styreansvarsforsikring (D&O)",
            "priority": "Anbefalt",
            "estimated_coverage_nok": coverage,
            "reason": "Personlig ansvar for styremedlemmer (aksjeloven). AS/ASA-organisert.",
        })

    # 5. Cyberforsikring — tech/finance/professional services
    if section in ("J", "K", "M", "N"):
        coverage = _mnok(max(5_000_000, revenue * 0.05))
        needs.append({
            "type": "Cyberforsikring",
            "priority": "Anbefalt",
            "estimated_coverage_nok": coverage,
            "reason": f"Høy digital eksponering i bransje {section} (IT/finans/rådgivning).",
        })

    # 6. Transportforsikring — logistics/manufacturing/trade
    if section in ("C", "G", "H"):
        coverage = _mnok(max(1_000_000, revenue * 0.02))
        needs.append({
            "type": "Transportforsikring",
            "priority": "Vurder",
            "estimated_coverage_nok": coverage,
            "reason": f"Vare- og godstransport vanlig i bransje {section} (industri/handel/transport).",
        })

    # 7. Nøkkelpersonforsikring — small but revenue-rich
    if 0 < employees < 50 and revenue > 5_000_000:
        coverage = _mnok(revenue * 0.5)
        needs.append({
            "type": "Nøkkelpersonforsikring",
            "priority": "Vurder",
            "estimated_coverage_nok": coverage,
            "reason": f"Liten bedrift ({employees} ansatte) med høy omsetning — sårbar for nøkkelpersontap.",
        })

    # 8. Kredittforsikring — wholesale or large revenue
    if section == "G" or revenue > 50_000_000:
        coverage = _mnok(max(1_000_000, revenue * 0.1))
        needs.append({
            "type": "Kredittforsikring",
            "priority": "Vurder",
            "estimated_coverage_nok": coverage,
            "reason": "Beskyttelse mot kundeinsolvens. Handel/høy omsetning øker kredittrisiko.",
        })

    # Sort: Kritisk → Anbefalt → Vurder
    _priority_order = {"Kritisk": 0, "Anbefalt": 1, "Vurder": 2}
    needs.sort(key=lambda x: _priority_order.get(x["priority"], 9))

    # Attach premium estimates
    for n in needs:
        n["estimated_annual_premium_nok"] = _estimate_premium(
            n["type"], n["estimated_coverage_nok"], section, employees, revenue
        )

    return needs


# ── Premium rate table ────────────────────────────────────────────────────────
# Rates are indicative Norwegian market ranges (% of coverage or % of payroll).
# Source: industry practice / Finans Norge statistics.

_PREMIUM_RATES: dict[str, tuple[float, float]] = {
    # (min_rate, max_rate) as fraction of coverage
    "Yrkesskadeforsikring":       (0.004, 0.008),   # 0.4–0.8% of lonnskostnad proxy
    "Ansvarsforsikring":          (0.003, 0.005),   # 0.3–0.5% of coverage
    "Eiendomsforsikring":         (0.001, 0.003),   # 0.1–0.3% of insured value
    "Styreansvarsforsikring (D&O)": (0.010, 0.020), # 1–2% of coverage
    "Cyberforsikring":            (0.015, 0.030),   # 1.5–3% — volatile market
    "Transportforsikring":        (0.003, 0.007),   # 0.3–0.7% of coverage
    "Nøkkelpersonforsikring":     (0.010, 0.015),   # 1–1.5% (life premium proxy)
    "Kredittforsikring":          (0.003, 0.006),   # 0.3–0.6% of credit exposure
}

_HIGH_RISK_SECTIONS = {"C", "F", "H", "I"}   # construction/manufacturing/transport/food


def _estimate_premium(
    insurance_type: str,
    coverage: float,
    section: str,
    employees: int,
    revenue: float,
) -> dict:
    """Return {low, mid, high} annual premium in NOK for the given insurance line."""
    rate_min, rate_max = _PREMIUM_RATES.get(insurance_type, (0.005, 0.010))

    # Risk loading: high-risk NACE sections pay ~20% more
    if section in _HIGH_RISK_SECTIONS:
        rate_min *= 1.20
        rate_max *= 1.20

    low = _mnok(coverage * rate_min)
    high = _mnok(coverage * rate_max)
    mid = _mnok((low + high) / 2)

    # Floor: minimum meaningful premium (avoid showing 0)
    floor = 5_000
    return {
        "low": max(low, floor),
        "mid": max(mid, floor),
        "high": max(high, floor),
    }


# ── LLM narrative ─────────────────────────────────────────────────────────────

def build_insurance_narrative(
    org: dict[str, Any],
    regn: dict[str, Any],
    needs: list[dict],
) -> str:
    """Generate a 2–3 sentence broker narrative via LLM (Claude → Gemini fallback).

    Returns empty string if no LLM key is configured.
    """
    from api.services.llm import _llm_answer_raw  # lazy import to avoid circular

    company_name = org.get("navn") or org.get("name") or "selskapet"
    revenue = regn.get("sum_driftsinntekter") or org.get("sum_driftsinntekter") or 0
    employees = int(regn.get("antall_ansatte") or org.get("antall_ansatte") or 0)
    nace = org.get("naeringskode1") or org.get("naeringskode") or ""
    section = _nace_section(nace)

    critical = [n["type"] for n in needs if n["priority"] == "Kritisk"]
    recommended = [n["type"] for n in needs if n["priority"] == "Anbefalt"]

    prompt = (
        f"Du er en erfaren norsk forsikringsmegler. Skriv 2–3 korte setninger (norsk) "
        f"som oppsummerer forsikringsbehovet for {company_name}. "
        f"Fakta: omsetning {revenue/1e6:.1f} MNOK, {employees} ansatte, bransje {section}. "
        f"Kritiske behov: {', '.join(critical) or 'ingen'}. "
        f"Anbefalte: {', '.join(recommended) or 'ingen'}. "
        f"Vær konkret og profesjonell. Ikke bruk punktlister."
    )
    try:
        return _llm_answer_raw(prompt) or ""
    except Exception:
        return ""
