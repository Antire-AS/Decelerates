"""Coverage gap analysis — compares active policies against rule-engine recommendations."""
from typing import Any

from sqlalchemy.orm import Session

from api.db import BrokerFirm, Company, CompanyHistory, Policy, PolicyStatus
from api.use_cases.insurance_needs import estimate_insurance_needs


# Maps each recommended type to keywords that match policy product_type values.
# Keys are lowercase substrings to search for in policy product_type (case-insensitive).
_MATCH_KEYWORDS: dict[str, list[str]] = {
    "yrkesskadeforsikring":       ["yrkesskade"],
    "ansvarsforsikring":          ["ansvar"],
    "eiendomsforsikring":         ["eiendom", "næringseiendom", "property"],
    "styreansvarsforsikring":     ["styreansvar", "d&o", "d & o"],
    "cyberforsikring":            ["cyber"],
    "transportforsikring":        ["transport", "varetransport"],
    "nøkkelpersonforsikring":     ["nøkkelperson", "key person"],
    "kredittforsikring":          ["kreditt", "credit"],
    "motorvognforsikring":        ["motorvogn", "bil", "kjøretøy", "motor"],
    "reiseforsikring":            ["reise"],
    "personforsikring":           ["person", "liv", "ulykke"],
    "avbruddsforsikring":         ["avbrudd", "driftsavbrudd", "business interruption"],
}


def _keywords_for(recommended_type: str) -> list[str]:
    key = recommended_type.lower()
    for k, keywords in _MATCH_KEYWORDS.items():
        if k in key or any(kw in key for kw in keywords):
            return keywords
    # fallback: use first word
    return [key.split()[0]] if key else []


def _policy_matches(policy_product: str, keywords: list[str]) -> bool:
    pt = policy_product.lower()
    return any(kw in pt for kw in keywords)


def analyze_coverage_gap(orgnr: str, firm_id: int, db: Session) -> dict[str, Any]:
    """Compare active policies against insurance needs recommendations.

    Returns:
        {
            "orgnr": str,
            "items": [
                {
                    "type": str,            # recommended coverage type
                    "priority": str,        # Kritisk / Anbefalt / Vurder
                    "reason": str,          # why it's recommended
                    "status": str,          # "covered" | "gap"
                    "estimated_coverage_nok": int | None,
                    "actual_coverage_nok": float | None,   # from matching policy
                    "actual_insurer": str | None,
                    "actual_policy_number": str | None,
                    "coverage_note": str | None,  # e.g. "Underdekning: 3 MNOK under anbefalt"
                }
            ],
            "covered_count": int,
            "gap_count": int,
            "total_count": int,
        }
    """
    # ── Load company data ─────────────────────────────────────────────────────
    company = db.query(Company).filter(Company.orgnr == orgnr).first()
    org: dict[str, Any] = {}
    regn: dict[str, Any] = {}

    if company:
        org = {
            "organisasjonsform_kode": company.organisasjonsform_kode,
            "naeringskode1":          company.naeringskode1,
            "naeringskode":           company.naeringskode1,
            "antall_ansatte":         company.antall_ansatte,
            "sum_driftsinntekter":    company.sum_driftsinntekter,
            "sum_eiendeler":          company.sum_eiendeler,
        }
        regn = {
            "sum_driftsinntekter": company.sum_driftsinntekter,
            "sum_eiendeler":       company.sum_eiendeler,
            "antall_ansatte":      company.antall_ansatte,
        }
        # Enrich from most recent history row if regnskap fields are missing
        if not company.sum_driftsinntekter:
            hist = (
                db.query(CompanyHistory)
                .filter(CompanyHistory.orgnr == orgnr)
                .order_by(CompanyHistory.year.desc())
                .first()
            )
            if hist:
                regn["sum_driftsinntekter"] = hist.revenue
                regn["sum_eiendeler"]       = hist.total_assets
                regn["antall_ansatte"]      = hist.antall_ansatte
                org["sum_driftsinntekter"]  = hist.revenue
                org["sum_eiendeler"]        = hist.total_assets
                org["antall_ansatte"]       = hist.antall_ansatte

    # ── Get recommendations from rule engine ──────────────────────────────────
    needs = estimate_insurance_needs(org, regn)

    # ── Load active policies ───────────────────────────────────────────────────
    active_policies = (
        db.query(Policy)
        .filter(
            Policy.orgnr == orgnr,
            Policy.firm_id == firm_id,
            Policy.status == PolicyStatus.active,
        )
        .all()
    )

    # ── Match each recommendation against policies ────────────────────────────
    items = []
    for need in needs:
        rec_type    = need["type"]
        priority    = need["priority"]
        reason      = need["reason"]
        est_cov     = need.get("estimated_coverage_nok")
        keywords    = _keywords_for(rec_type)

        matching = [p for p in active_policies if _policy_matches(p.product_type, keywords)]
        best = matching[0] if matching else None

        if best:
            status           = "covered"
            actual_cov       = best.coverage_amount_nok
            actual_insurer   = best.insurer
            actual_policy_nr = best.policy_number

            # Flag potential under-coverage (actual < 70 % of recommended)
            coverage_note = None
            if est_cov and actual_cov and actual_cov < est_cov * 0.7:
                diff_mnok = (est_cov - actual_cov) / 1_000_000
                coverage_note = f"Mulig underdekning: {diff_mnok:.1f} MNOK under anbefalt nivå"
        else:
            status           = "gap"
            actual_cov       = None
            actual_insurer   = None
            actual_policy_nr = None
            coverage_note    = None

        items.append({
            "type":                   rec_type,
            "priority":               priority,
            "reason":                 reason,
            "status":                 status,
            "estimated_coverage_nok": est_cov,
            "actual_coverage_nok":    actual_cov,
            "actual_insurer":         actual_insurer,
            "actual_policy_number":   actual_policy_nr,
            "coverage_note":          coverage_note,
        })

    covered = sum(1 for i in items if i["status"] == "covered")

    return {
        "orgnr":         orgnr,
        "items":         items,
        "covered_count": covered,
        "gap_count":     len(items) - covered,
        "total_count":   len(items),
    }


def get_companies_with_gaps(firm_id: int, db: Session) -> list[dict]:
    """Return all companies in the firm's book that have at least one coverage gap."""
    orgnrs = [
        r.orgnr
        for r in db.query(Policy.orgnr)
        .filter(Policy.firm_id == firm_id, Policy.status == PolicyStatus.active)
        .distinct()
        .all()
    ]
    results = []
    for orgnr in orgnrs:
        try:
            analysis = analyze_coverage_gap(orgnr, firm_id, db)
            if analysis["gap_count"] > 0:
                company = db.query(Company).filter(Company.orgnr == orgnr).first()
                results.append({
                    "orgnr":       orgnr,
                    "navn":        company.navn if company else orgnr,
                    "gap_count":   analysis["gap_count"],
                    "total_count": analysis["total_count"],
                    "gaps": [
                        {"type": i["type"], "priority": i["priority"]}
                        for i in analysis["items"]
                        if i["status"] == "gap"
                    ],
                })
        except Exception:
            continue
    return results
