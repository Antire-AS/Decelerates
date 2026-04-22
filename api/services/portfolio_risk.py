"""Portfolio-level risk aggregation using Altman Z'' snapshots.

One `compute_and_store_snapshot(portfolio_id)` call records the current
Altman Z'' for every company in a portfolio. `get_portfolio_risk_summary`
reads the two most recent snapshot batches to compute zone distribution,
zone transitions (prev → curr), and sum of annual premium for companies
now in the distress zone.

Design notes:
- Reads `regnskap_raw` from the Company row; if missing or incomplete
  (banks lack the working-capital split) falls back to the most recent
  `company_history.raw`.
- Snapshots are append-only. A "batch" is every row sharing the same
  `snapshot_at` within a 1-minute window (all companies in a portfolio
  get the same timestamp because we write them in one loop).
- If a portfolio has only one snapshot batch, transitions is [].
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc
from sqlalchemy.orm import Session

from api.db import (
    Company,
    CompanyHistory,
    Policy,
    PolicyStatus,
    Portfolio,
    PortfolioCompany,
    PortfolioRiskSnapshot,
)
from api.domain.exceptions import NotFoundError
from api.risk import compute_altman_z_score


UNKNOWN_ZONE = "unknown"


def _latest_regn_for(orgnr: str, db: Session) -> Dict[str, Any]:
    """Prefer the company's regnskap_raw; fall back to the most recent
    company_history.raw when the primary row is empty or missing the
    Altman-required fields (banks, thin extractions)."""
    company = db.query(Company).filter(Company.orgnr == orgnr).first()
    regn: Dict[str, Any] = (
        dict(company.regnskap_raw) if company and company.regnskap_raw else {}
    )
    needed = ("sum_omloepsmidler", "short_term_debt", "sum_opptjent_egenkapital")
    if all(regn.get(k) is not None for k in needed):
        return regn
    row = (
        db.query(CompanyHistory)
        .filter(CompanyHistory.orgnr == orgnr)
        .order_by(CompanyHistory.year.desc())
        .first()
    )
    if row and row.raw:
        return dict(row.raw)
    return regn


def _assert_portfolio_visible(portfolio_id: int, firm_id: int, db: Session) -> None:
    """Load the portfolio scoped to the caller's firm. Firm-visible means
    either the portfolio belongs to this firm or is a system-wide portfolio
    (firm_id NULL). Raises NotFoundError for both "doesn't exist" and
    "belongs to another firm" so a caller can't probe cross-firm IDs."""
    found = (
        db.query(Portfolio)
        .filter(
            Portfolio.id == portfolio_id,
            (Portfolio.firm_id == firm_id) | (Portfolio.firm_id.is_(None)),
        )
        .first()
    )
    if not found:
        raise NotFoundError(f"Portfolio {portfolio_id} not found")


def compute_and_store_snapshot(
    portfolio_id: int, firm_id: int, db: Session
) -> datetime:
    """Compute Altman Z'' for every company in the portfolio and persist
    a row per company in `portfolio_risk_snapshot`. Returns the common
    snapshot timestamp so the caller can log it."""
    _assert_portfolio_visible(portfolio_id, firm_id, db)
    members = (
        db.query(PortfolioCompany)
        .filter(PortfolioCompany.portfolio_id == portfolio_id)
        .all()
    )
    taken_at = datetime.now(timezone.utc)
    for m in members:
        regn = _latest_regn_for(m.orgnr, db)
        altman = compute_altman_z_score(regn) if regn else None
        db.add(
            PortfolioRiskSnapshot(
                portfolio_id=portfolio_id,
                orgnr=m.orgnr,
                z_score=altman["z_score"] if altman else None,
                zone=altman["zone"] if altman else UNKNOWN_ZONE,
                score_20=altman["score_20"] if altman else None,
                snapshot_at=taken_at,
            )
        )
    db.commit()
    return taken_at


def _latest_two_batch_timestamps(
    portfolio_id: int, db: Session
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Distinct snapshot_at values, newest first. A portfolio with zero
    or one snapshot batch returns (None, None) or (latest, None)."""
    rows = (
        db.query(PortfolioRiskSnapshot.snapshot_at)
        .filter(PortfolioRiskSnapshot.portfolio_id == portfolio_id)
        .order_by(desc(PortfolioRiskSnapshot.snapshot_at))
        .all()
    )
    seen: List[datetime] = []
    for (ts,) in rows:
        if not seen or seen[-1] != ts:
            seen.append(ts)
        if len(seen) == 2:
            break
    return (seen[0] if seen else None, seen[1] if len(seen) > 1 else None)


def _load_batch(
    portfolio_id: int, taken_at: datetime, db: Session
) -> Dict[str, PortfolioRiskSnapshot]:
    rows = (
        db.query(PortfolioRiskSnapshot)
        .filter(
            PortfolioRiskSnapshot.portfolio_id == portfolio_id,
            PortfolioRiskSnapshot.snapshot_at == taken_at,
        )
        .all()
    )
    return {r.orgnr: r for r in rows}


def _zone_counts(batch: Dict[str, PortfolioRiskSnapshot]) -> Dict[str, int]:
    counts = {"safe": 0, "grey": 0, "distress": 0, UNKNOWN_ZONE: 0}
    for r in batch.values():
        counts[r.zone or UNKNOWN_ZONE] = counts.get(r.zone or UNKNOWN_ZONE, 0) + 1
    return counts


def _transitions(
    curr: Dict[str, PortfolioRiskSnapshot],
    prev: Dict[str, PortfolioRiskSnapshot],
    db: Session,
) -> List[Dict[str, Any]]:
    """Rows where zone changed between prev and curr snapshot. Enriches with
    company navn so the UI doesn't need a second lookup."""
    if not prev:
        return []
    moved_orgnrs = [
        orgnr
        for orgnr, r in curr.items()
        if prev.get(orgnr) and prev[orgnr].zone != r.zone
    ]
    if not moved_orgnrs:
        return []
    navn_map = dict(
        db.query(Company.orgnr, Company.navn)
        .filter(Company.orgnr.in_(moved_orgnrs))
        .all()
    )
    out: List[Dict[str, Any]] = []
    for orgnr in moved_orgnrs:
        c = curr[orgnr]
        p = prev[orgnr]
        out.append(
            {
                "orgnr": orgnr,
                "navn": navn_map.get(orgnr),
                "prev_zone": p.zone,
                "curr_zone": c.zone,
                "prev_z": p.z_score,
                "curr_z": c.z_score,
                "delta_z": (c.z_score - p.z_score)
                if (c.z_score is not None and p.z_score is not None)
                else None,
            }
        )
    return out


def _premium_at_risk(batch: Dict[str, PortfolioRiskSnapshot], db: Session) -> float:
    """Sum annual premium of ACTIVE policies for companies currently in the
    distress zone. Broker's question: 'how much of my book is exposed if
    these clients fold in the next 12 months?'"""
    distress_orgnrs = [o for o, r in batch.items() if r.zone == "distress"]
    if not distress_orgnrs:
        return 0.0
    total = (
        db.query(Policy.annual_premium_nok)
        .filter(
            Policy.orgnr.in_(distress_orgnrs),
            Policy.status == PolicyStatus.active,
            Policy.annual_premium_nok.isnot(None),
        )
        .all()
    )
    return float(sum((p[0] or 0.0) for p in total))


def _company_rows(
    batch: Dict[str, PortfolioRiskSnapshot], db: Session
) -> List[Dict[str, Any]]:
    """All portfolio companies ranked by Z'' ascending (worst first).
    Unknown-zone rows sink to the bottom regardless of numerical order."""
    navn_map = dict(
        db.query(Company.orgnr, Company.navn)
        .filter(Company.orgnr.in_(list(batch.keys())))
        .all()
    )

    def sort_key(r: PortfolioRiskSnapshot) -> Tuple[int, float]:
        if r.z_score is None:
            return (1, 0.0)
        return (0, r.z_score)

    ordered = sorted(batch.values(), key=sort_key)
    return [
        {
            "orgnr": r.orgnr,
            "navn": navn_map.get(r.orgnr),
            "zone": r.zone,
            "z_score": r.z_score,
            "score_20": r.score_20,
        }
        for r in ordered
    ]


def get_portfolio_risk_summary(
    portfolio_id: int, firm_id: int, db: Session
) -> Dict[str, Any]:
    """Read the most-recent snapshot batch for a portfolio and return the
    dashboard payload: zones histogram, zone transitions vs previous batch,
    premium-at-risk (distress zone), and a ranked company list."""
    _assert_portfolio_visible(portfolio_id, firm_id, db)
    curr_at, prev_at = _latest_two_batch_timestamps(portfolio_id, db)
    if curr_at is None:
        return {
            "portfolio_id": portfolio_id,
            "snapshot_at": None,
            "prev_snapshot_at": None,
            "zones": {"safe": 0, "grey": 0, "distress": 0, UNKNOWN_ZONE: 0},
            "transitions": [],
            "premium_at_risk_nok": 0.0,
            "companies": [],
        }
    curr = _load_batch(portfolio_id, curr_at, db)
    prev = _load_batch(portfolio_id, prev_at, db) if prev_at else {}
    return {
        "portfolio_id": portfolio_id,
        "snapshot_at": curr_at.isoformat(),
        "prev_snapshot_at": prev_at.isoformat() if prev_at else None,
        "zones": _zone_counts(curr),
        "transitions": _transitions(curr, prev, db),
        "premium_at_risk_nok": _premium_at_risk(curr, db),
        "companies": _company_rows(curr, db),
    }
