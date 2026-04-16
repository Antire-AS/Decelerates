"""Insurer matching agent — scores and ranks insurers for a company.

Combines three signals:
  1. Appetite match — does the insurer cover this product type?
  2. Historical win rate — from Submission data (quoted / total)
  3. Profile fit — does the insurer's appetite match the company's industry?

Returns top N recommendations with LLM-generated Norwegian reasoning.

This is PR 4 of the AI Agent Acceleration Roadmap.
"""
import logging
from typing import Any

from sqlalchemy.orm import Session

from api.db import Company, Insurer, Submission

_log = logging.getLogger(__name__)


def _score_insurer(
    insurer: Insurer,
    product_types: list[str],
    win_rates: dict[int, float],
) -> float:
    """Score an insurer 0–1 based on appetite match + historical win rate."""
    appetite = [a.lower() for a in (insurer.appetite or [])]

    # Appetite match: what fraction of requested product types does this insurer cover?
    matched = sum(
        1 for pt in product_types
        if any(pt.lower() in a or a in pt.lower() for a in appetite)
    )
    appetite_score = matched / len(product_types) if product_types else 0.0

    # Win rate from submissions (0–1)
    win_rate = win_rates.get(insurer.id, 0.0) / 100.0

    return 0.6 * appetite_score + 0.4 * win_rate


def _compute_win_rates(firm_id: int, db: Session) -> dict[int, float]:
    """Return {insurer_id: win_rate_pct} from submission data."""
    subs = db.query(Submission).filter(Submission.firm_id == firm_id).all()
    by_insurer: dict[int, dict[str, int]] = {}
    for s in subs:
        iid = s.insurer_id
        if iid not in by_insurer:
            by_insurer[iid] = {"total": 0, "quoted": 0}
        by_insurer[iid]["total"] += 1
        if s.status and s.status.value == "quoted":
            by_insurer[iid]["quoted"] += 1
    return {
        iid: round(stats["quoted"] / stats["total"] * 100, 1) if stats["total"] else 0.0
        for iid, stats in by_insurer.items()
    }


def _generate_reasoning(
    insurer_name: str,
    score: float,
    company_name: str,
    product_types: list[str],
) -> str:
    """LLM-generated Norwegian reasoning for the recommendation."""
    from api.services.llm import _llm_answer_raw
    products = ", ".join(product_types) if product_types else "generell forsikring"
    prompt = (
        f"Du er en norsk forsikringsmegler. Skriv en kort anbefaling (2-3 setninger) "
        f"for hvorfor {insurer_name} er et godt valg for {company_name} "
        f"innen {products}. Skår: {score:.0%}. Vær konkret og profesjonell."
    )
    return _llm_answer_raw(prompt) or f"{insurer_name} er anbefalt basert på appetittmatch og historisk tilslagsrate."


def _resolve_product_types(
    orgnr: str, firm_id: int, product_types: list[str] | None, db: Session,
) -> list[str]:
    """Auto-derive product types from coverage gaps if not explicitly provided."""
    if product_types:
        return product_types
    from api.services.coverage_gap import analyze_coverage_gap
    try:
        gaps = analyze_coverage_gap(orgnr, firm_id, db)
        return [i["type"] for i in gaps.get("items", []) if i["status"] == "gap"]
    except Exception:
        return []


def _build_recommendations(
    top: list[tuple[Insurer, float]],
    win_rates: dict[int, float],
    company_name: str,
    product_types: list[str],
) -> list[dict[str, Any]]:
    """Build the recommendation list with LLM reasoning for each insurer."""
    return [
        {
            "insurer_id": ins.id,
            "insurer_name": ins.name,
            "score": round(score, 3),
            "win_rate_pct": win_rates.get(ins.id, 0.0),
            "appetite": ins.appetite or [],
            "reasoning": _generate_reasoning(ins.name, score, company_name, product_types),
            "product_types_matched": product_types,
        }
        for ins, score in top
    ]


class InsurerMatchingService:
    def __init__(self, db: Session):
        self.db = db

    def recommend_insurers(
        self, orgnr: str, firm_id: int, product_types: list[str] | None,
        top_n: int = 3,
    ) -> dict[str, Any]:
        """Score and rank insurers for a company. Returns top N with reasoning."""
        company = self.db.query(Company).filter(Company.orgnr == orgnr).first()
        company_name = company.navn if company else orgnr
        product_types = _resolve_product_types(orgnr, firm_id, product_types, self.db)

        insurers = self.db.query(Insurer).filter(Insurer.firm_id == firm_id).all()
        if not insurers:
            return {"recommendations": [], "company": {"orgnr": orgnr, "navn": company_name}}

        win_rates = _compute_win_rates(firm_id, self.db)
        scored = sorted(
            [(ins, _score_insurer(ins, product_types, win_rates)) for ins in insurers],
            key=lambda x: x[1], reverse=True,
        )
        return {
            "recommendations": _build_recommendations(scored[:top_n], win_rates, company_name, product_types),
            "company": {"orgnr": orgnr, "navn": company_name},
        }


# Backward compat
def recommend_insurers(
    orgnr: str, firm_id: int, product_types: list[str] | None,
    db: Session, top_n: int = 3,
) -> dict[str, Any]:
    return InsurerMatchingService(db).recommend_insurers(orgnr, firm_id, product_types, top_n)
