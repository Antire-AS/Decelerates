"""Portfolio analytics — policy premium aggregation and concentration breakdown."""

from datetime import date

from sqlalchemy.orm import Session

from api.db import PortfolioCompany, Company, Policy, PolicyStatus
import logging

logger = logging.getLogger(__name__)


def _insurer_concentration(policies: list, total_premium: float) -> list:
    insurer_map: dict[str, dict] = {}
    for p in policies:
        ins = p.insurer or "Ukjent"
        if ins not in insurer_map:
            insurer_map[ins] = {"insurer": ins, "policy_count": 0, "premium_nok": 0.0}
        insurer_map[ins]["policy_count"] += 1
        insurer_map[ins]["premium_nok"] += p.annual_premium_nok or 0
    rows = sorted(insurer_map.values(), key=lambda x: x["premium_nok"], reverse=True)
    for row in rows:
        row["share_pct"] = (
            round(row["premium_nok"] / total_premium * 100, 1) if total_premium else 0
        )
    return rows


def _product_concentration(policies: list) -> list:
    product_map: dict[str, dict] = {}
    for p in policies:
        pt = p.product_type or "Ukjent"
        if pt not in product_map:
            product_map[pt] = {"product_type": pt, "count": 0, "premium_nok": 0.0}
        product_map[pt]["count"] += 1
        product_map[pt]["premium_nok"] += p.annual_premium_nok or 0
    return sorted(product_map.values(), key=lambda x: x["premium_nok"], reverse=True)


def _nace_section(nace) -> str:
    from api.constants import _NACE_SECTION_MAP

    if not nace:
        return "?"
    try:
        code = int(str(nace).split(".")[0])
        for rng, s in _NACE_SECTION_MAP:
            if code in rng:
                return s
    except (ValueError, AttributeError):
        pass
    return "?"


def _rev_band(rev) -> str:
    if not rev:
        return "Ukjent"
    if rev < 10_000_000:
        return "<10 MNOK"
    if rev < 100_000_000:
        return "10–100 MNOK"
    if rev < 1_000_000_000:
        return "100 MNOK–1 BNOK"
    return ">1 BNOK"


class PortfolioAnalyticsService:
    def __init__(self, db: Session):
        self.db = db

    def get_analytics(self, portfolio_id: int, firm_id: int, get_portfolio_fn) -> dict:
        """Aggregate policy premium data for all companies in the portfolio."""
        get_portfolio_fn(
            portfolio_id, firm_id
        )  # raises NotFoundError if missing or wrong firm
        orgnrs = [
            pc.orgnr
            for pc in self.db.query(PortfolioCompany)
            .filter(PortfolioCompany.portfolio_id == portfolio_id)
            .all()
        ]
        if not orgnrs:
            return {
                "total_annual_premium_nok": 0,
                "active_policy_count": 0,
                "insurer_concentration": [],
                "product_concentration": [],
                "upcoming_renewals_90d": 0,
                "upcoming_renewals_30d": 0,
            }
        policies = (
            self.db.query(Policy)
            .filter(
                Policy.orgnr.in_(orgnrs),
                Policy.firm_id == firm_id,
                Policy.status == PolicyStatus.active,
            )
            .all()
        )
        today = date.today()
        total_premium = sum(p.annual_premium_nok or 0 for p in policies)
        renewals_90 = sum(
            1
            for p in policies
            if p.renewal_date and 0 <= (p.renewal_date - today).days <= 90
        )
        renewals_30 = sum(
            1
            for p in policies
            if p.renewal_date and 0 <= (p.renewal_date - today).days <= 30
        )
        return {
            "total_annual_premium_nok": round(total_premium),
            "active_policy_count": len(policies),
            "insurer_concentration": _insurer_concentration(policies, total_premium),
            "product_concentration": _product_concentration(policies),
            "upcoming_renewals_90d": renewals_90,
            "upcoming_renewals_30d": renewals_30,
        }

    def get_concentration(self, portfolio_id: int, get_portfolio_fn) -> dict:
        """Return portfolio concentration breakdown by industry, geography, and revenue size."""
        from api.constants import NACE_BENCHMARKS

        get_portfolio_fn(portfolio_id)  # raises NotFoundError if missing
        orgnrs = [
            r.orgnr
            for r in self.db.query(PortfolioCompany)
            .filter(PortfolioCompany.portfolio_id == portfolio_id)
            .all()
        ]
        companies = self.db.query(Company).filter(Company.orgnr.in_(orgnrs)).all()
        industry: dict[str, dict] = {}
        geography: dict[str, int] = {}
        size: dict[str, int] = {}
        total_revenue = 0.0
        for c in companies:
            sec = _nace_section(c.naeringskode1)
            label = NACE_BENCHMARKS.get(sec, {}).get("industry", sec)
            industry.setdefault(
                sec, {"section": sec, "label": label, "count": 0, "revenue": 0}
            )
            industry[sec]["count"] += 1
            industry[sec]["revenue"] += c.sum_driftsinntekter or 0
            geography[c.kommune or "Ukjent"] = (
                geography.get(c.kommune or "Ukjent", 0) + 1
            )
            band = _rev_band(c.sum_driftsinntekter)
            size[band] = size.get(band, 0) + 1
            total_revenue += c.sum_driftsinntekter or 0
        geo_sorted = sorted(geography.items(), key=lambda x: x[1], reverse=True)[:10]
        return {
            "portfolio_id": portfolio_id,
            "total_companies": len(companies),
            "total_revenue": total_revenue,
            "by_industry": sorted(
                industry.values(), key=lambda x: x["count"], reverse=True
            ),
            "by_geography": [{"kommune": k, "count": v} for k, v in geo_sorted],
            "by_size": [{"band": k, "count": v} for k, v in size.items()],
        }


# Backward compat
def get_analytics(
    portfolio_id: int, firm_id: int, db: Session, get_portfolio_fn
) -> dict:
    return PortfolioAnalyticsService(db).get_analytics(
        portfolio_id, firm_id, get_portfolio_fn
    )


def get_concentration(portfolio_id: int, db: Session, get_portfolio_fn) -> dict:
    return PortfolioAnalyticsService(db).get_concentration(
        portfolio_id, get_portfolio_fn
    )
