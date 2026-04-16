"""Coverage gap analysis — compares active policies against rule-engine recommendations."""
from typing import Any

from sqlalchemy.orm import Session

from api.db import Company, CompanyHistory, Policy, PolicyStatus
from api.use_cases.insurance_needs import estimate_insurance_needs
import logging

logger = logging.getLogger(__name__)



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
    "avbruddsforsikring":        ["avbrudd", "driftsavbrudd", "business interruption"],
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


def _load_company_context(orgnr: str, db: Session) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build (org, regn) dicts for the rule engine, falling back to history rows
    when the Company row is missing the financial figures."""
    company = db.query(Company).filter(Company.orgnr == orgnr).first()
    if not company:
        return {}, {}

    org: dict[str, Any] = {
        "organisasjonsform_kode": company.organisasjonsform_kode,
        "naeringskode1":          company.naeringskode1,
        "naeringskode":           company.naeringskode1,
        "antall_ansatte":         company.antall_ansatte,
        "sum_driftsinntekter":    company.sum_driftsinntekter,
        "sum_eiendeler":          company.sum_eiendeler,
    }
    regn: dict[str, Any] = {
        "sum_driftsinntekter": company.sum_driftsinntekter,
        "sum_eiendeler":       company.sum_eiendeler,
        "antall_ansatte":      company.antall_ansatte,
    }

    if not company.sum_driftsinntekter:
        hist = (
            db.query(CompanyHistory)
            .filter(CompanyHistory.orgnr == orgnr)
            .order_by(CompanyHistory.year.desc())
            .first()
        )
        if hist:
            for d in (org, regn):
                d["sum_driftsinntekter"] = hist.revenue
                d["sum_eiendeler"]       = hist.total_assets
                d["antall_ansatte"]      = hist.antall_ansatte
    return org, regn


def _build_gap_item(need: dict[str, Any], active_policies: list[Policy]) -> dict[str, Any]:
    """Match one recommendation against active policies and return one report row."""
    rec_type = need["type"]
    est_cov  = need.get("estimated_coverage_nok")
    keywords = _keywords_for(rec_type)
    matching = [p for p in active_policies if _policy_matches(p.product_type, keywords)]
    best = matching[0] if matching else None

    if best:
        coverage_note = None
        if est_cov and best.coverage_amount_nok and best.coverage_amount_nok < est_cov * 0.7:
            diff_mnok = (est_cov - best.coverage_amount_nok) / 1_000_000
            coverage_note = f"Mulig underdekning: {diff_mnok:.1f} MNOK under anbefalt nivå"
        return {
            "type":                   rec_type,
            "priority":               need["priority"],
            "reason":                 need["reason"],
            "status":                 "covered",
            "estimated_coverage_nok": est_cov,
            "actual_coverage_nok":    best.coverage_amount_nok,
            "actual_insurer":         best.insurer,
            "actual_policy_number":   best.policy_number,
            "coverage_note":          coverage_note,
        }
    return {
        "type":                   rec_type,
        "priority":               need["priority"],
        "reason":                 need["reason"],
        "status":                 "gap",
        "estimated_coverage_nok": est_cov,
        "actual_coverage_nok":    None,
        "actual_insurer":         None,
        "actual_policy_number":   None,
        "coverage_note":          None,
    }


class CoverageGapService:
    def __init__(self, db: Session):
        self.db = db

    def analyze_coverage_gap(self, orgnr: str, firm_id: int) -> dict[str, Any]:
        """Compare active policies against insurance-need recommendations.

        Returns a dict shaped like:
            {orgnr, items: [{type, priority, reason, status, estimated_coverage_nok,
            actual_coverage_nok, actual_insurer, actual_policy_number, coverage_note}],
            covered_count, gap_count, total_count}
        """
        org, regn = _load_company_context(orgnr, self.db)
        needs = estimate_insurance_needs(org, regn)

        active_policies = (
            self.db.query(Policy)
            .filter(
                Policy.orgnr == orgnr,
                Policy.firm_id == firm_id,
                Policy.status == PolicyStatus.active,
            )
            .all()
        )

        items = [_build_gap_item(need, active_policies) for need in needs]
        covered = sum(1 for i in items if i["status"] == "covered")

        return {
            "orgnr":         orgnr,
            "items":         items,
            "covered_count": covered,
            "gap_count":     len(items) - covered,
            "total_count":   len(items),
        }

    def get_companies_with_gaps(self, firm_id: int) -> list[dict]:
        """Return all companies in the firm's book that have at least one coverage gap."""
        orgnrs = [
            r.orgnr
            for r in self.db.query(Policy.orgnr)
            .filter(Policy.firm_id == firm_id, Policy.status == PolicyStatus.active)
            .distinct()
            .all()
        ]
        results = []
        for orgnr in orgnrs:
            try:
                analysis = analyze_coverage_gap(orgnr, firm_id, self.db)
                if analysis["gap_count"] > 0:
                    company = self.db.query(Company).filter(Company.orgnr == orgnr).first()
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


# Backward compat
def analyze_coverage_gap(orgnr: str, firm_id: int, db: Session) -> dict[str, Any]:
    return CoverageGapService(db).analyze_coverage_gap(orgnr, firm_id)


def get_companies_with_gaps(firm_id: int, db: Session) -> list[dict]:
    return CoverageGapService(db).get_companies_with_gaps(firm_id)
