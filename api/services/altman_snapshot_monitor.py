"""Nightly Altman-zone snapshot monitor.

The Phase D `portfolio_risk_snapshot` table is useful only if snapshots
get taken regularly. Without scheduled refreshes, zone transitions are
whatever the last broker-initiated snapshot recorded — weeks stale for
portfolios no one has visited.

This service:

  1. Iterates every Portfolio row
  2. Calls `compute_and_store_snapshot(portfolio_id, firm_id, db)` to
     record the current Altman Z'' zone for each member company
  3. Diffs the new batch against the previous batch
  4. For every company that moved zones, posts a notification to every
     user in the portfolio's firm so someone sees it next login

Called from POST /admin/refresh-altman-snapshots which is wired to a
nightly GitHub Actions cron at 04:30 UTC.

Designed to be safe under duplicate invocation — a cron misfire just
produces an extra snapshot batch for the day (nice to have, not a bug).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

from api.db import (
    Company,
    NotificationKind,
    Portfolio,
    PortfolioCompany,
    User,
)
from api.services.notification_inbox_service import create_notification_for_users_safe
from api.services.portfolio_risk import (
    _latest_two_batch_timestamps,
    _load_batch,
    compute_and_store_snapshot,
)

_log = logging.getLogger(__name__)

# Only distress-direction transitions are notification-worthy — going
# safe → grey and grey → distress is what changes an underwriter's
# posture. A company recovering from distress is good news but doesn't
# need a push.
_WORSENING_TRANSITIONS = {
    ("safe", "grey"),
    ("safe", "distress"),
    ("grey", "distress"),
}


def _users_in_firm(firm_id: int | None, db: Session) -> list[int]:
    """Users who should see notifications for a portfolio. When the
    portfolio has no firm_id (system-wide / demo portfolio) we skip
    notifications — there's no well-defined audience."""
    if firm_id is None:
        return []
    rows = db.query(User.id).filter(User.firm_id == firm_id).all()
    return [uid for (uid,) in rows]


def _fire_zone_change_notifications(
    portfolio: Portfolio,
    transitions: list[dict],
    db: Session,
) -> int:
    """Post one notification per transitioning company per user in the
    firm. Returns the number of notifications written."""
    if not transitions:
        return 0
    user_ids = _users_in_firm(portfolio.firm_id, db)
    if not user_ids:
        return 0
    written = 0
    for t in transitions:
        title = f"{t['navn'] or t['orgnr']}: {t['prev_zone']} → {t['curr_zone']}"
        message = (
            f"Altman Z″ beveget seg fra {t['prev_zone']} til {t['curr_zone']} "
            f'i porteføljen "{portfolio.name}".'
        )
        link = f"/portfolio/{portfolio.id}/altman-risk"
        create_notification_for_users_safe(
            db,
            user_ids=user_ids,
            firm_id=portfolio.firm_id or 0,
            kind=NotificationKind.coverage_gap,
            title=title,
            message=message,
            orgnr=t["orgnr"],
            link=link,
        )
        written += len(user_ids)
    return written


def _transitions_of_concern(portfolio_id: int, db: Session) -> list[dict]:
    """Return zone transitions between the two most recent snapshot
    batches — only worsening direction. Each entry has orgnr, navn,
    prev_zone, curr_zone."""
    curr_at, prev_at = _latest_two_batch_timestamps(portfolio_id, db)
    if curr_at is None or prev_at is None:
        return []
    curr = _load_batch(portfolio_id, curr_at, db)
    prev = _load_batch(portfolio_id, prev_at, db)
    if not prev or not curr:
        return []
    moved: list[dict] = []
    for orgnr, c in curr.items():
        p = prev.get(orgnr)
        if not p or p.zone == c.zone:
            continue
        if (p.zone, c.zone) not in _WORSENING_TRANSITIONS:
            continue
        moved.append(
            {
                "orgnr": orgnr,
                "prev_zone": p.zone,
                "curr_zone": c.zone,
            }
        )
    if not moved:
        return []
    # Hydrate navn from Company table (single query, not per-row).
    navn_map = dict(
        db.query(Company.orgnr, Company.navn)
        .filter(Company.orgnr.in_([m["orgnr"] for m in moved]))
        .all()
    )
    for m in moved:
        m["navn"] = navn_map.get(m["orgnr"])
    return moved


def refresh_all_altman_snapshots(db: Session) -> Dict[str, Any]:
    """Iterate every portfolio, take a fresh Altman snapshot, detect
    worsening zone transitions, post notifications. Returns a summary
    dict for the cron logs so failures are visible in the Actions UI."""
    started = datetime.now(timezone.utc)
    portfolios = db.query(Portfolio).all()
    snapshots_taken = 0
    transitions_fired = 0
    portfolios_skipped = 0
    for p in portfolios:
        member_count = (
            db.query(PortfolioCompany)
            .filter(PortfolioCompany.portfolio_id == p.id)
            .count()
        )
        if member_count == 0:
            portfolios_skipped += 1
            continue
        firm_id = p.firm_id if p.firm_id is not None else 0
        try:
            compute_and_store_snapshot(p.id, firm_id, db)
            snapshots_taken += 1
        except Exception as exc:
            _log.warning("altman snapshot failed for portfolio %s: %s", p.id, exc)
            continue
        moved = _transitions_of_concern(p.id, db)
        transitions_fired += _fire_zone_change_notifications(p, moved, db)
    return {
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "portfolios_total": len(portfolios),
        "portfolios_skipped_empty": portfolios_skipped,
        "snapshots_taken": snapshots_taken,
        "notifications_written": transitions_fired,
    }
