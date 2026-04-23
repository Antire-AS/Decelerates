"""Nightly company-news refresh monitor.

Phase H shipped on-demand news fetching — brokers click "Oppdater" on
a company's Nyheter tab to refresh. Without a cron, a client who hasn't
been opened in weeks silently accumulates blind spots on the broker's
book.

This service iterates every company that appears in at least one
portfolio and calls `refresh_company_news` per company. Serper's free
tier gives us 2500 credits/month; we budget generously — the query is
biased toward material keywords (I5) so each refresh tends to return
≤10 hits, most of which are already stored (dedupe by URL). In practice
expect ~20 new articles / night across a 100-client book.

Called from POST /admin/refresh-all-news wired to a nightly GitHub
Actions cron at 03:30 UTC (before the Altman snapshot cron so any
material news is in the DB when the snapshot diff runs).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

from api.db import Company, PortfolioCompany
from api.services.news_service import refresh_company_news

_log = logging.getLogger(__name__)


def _companies_in_portfolios(db: Session) -> list[str]:
    """Distinct orgnrs that appear in at least one portfolio. We only
    refresh news for companies a broker actually tracks — otherwise a
    single visit to an unrelated /search/123 would enrol it in the
    nightly budget forever."""
    rows = (
        db.query(PortfolioCompany.orgnr)
        .join(Company, Company.orgnr == PortfolioCompany.orgnr)
        .distinct()
        .all()
    )
    return [r[0] for r in rows]


def refresh_all_news(db: Session) -> Dict[str, Any]:
    """Iterate portfolio companies, refresh news per company, return
    totals. Individual-company failures are logged and skipped — one
    bad response shouldn't kill the whole run."""
    started = datetime.now(timezone.utc)
    orgnrs = _companies_in_portfolios(db)
    refreshed = 0
    articles_added = 0
    failures = 0
    for orgnr in orgnrs:
        try:
            added = refresh_company_news(orgnr, db)
        except Exception as exc:
            _log.warning("news refresh failed for %s: %s", orgnr, exc)
            failures += 1
            continue
        refreshed += 1
        articles_added += added
    return {
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "orgnrs_refreshed": refreshed,
        "orgnrs_failed": failures,
        "articles_added": articles_added,
    }
