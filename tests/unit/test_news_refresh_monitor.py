"""Unit tests for the nightly news-refresh monitor.

Pins the "refresh only portfolio companies" invariant — we don't want
a single /search/<random> visit enrolling a company in the nightly
Serper budget forever.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from api.services import news_refresh_monitor


def test_refresh_returns_totals_when_no_portfolio_companies():
    db = MagicMock()
    with patch.object(
        news_refresh_monitor, "_companies_in_portfolios", return_value=[]
    ):
        result = news_refresh_monitor.refresh_all_news(db)
    assert result["orgnrs_refreshed"] == 0
    assert result["orgnrs_failed"] == 0
    assert result["articles_added"] == 0


def test_refresh_aggregates_per_company_counts():
    db = MagicMock()
    with (
        patch.object(
            news_refresh_monitor,
            "_companies_in_portfolios",
            return_value=["111111111", "222222222", "333333333"],
        ),
        patch.object(
            news_refresh_monitor,
            "refresh_company_news",
            side_effect=[3, 0, 5],  # 3 + 0 + 5 = 8 new articles total
        ),
    ):
        result = news_refresh_monitor.refresh_all_news(db)
    assert result["orgnrs_refreshed"] == 3
    assert result["orgnrs_failed"] == 0
    assert result["articles_added"] == 8


def test_refresh_skips_failing_company_but_continues_others():
    """One 500 from Serper for company A shouldn't stop us refreshing B."""
    db = MagicMock()

    def _refresh(orgnr: str, db_session) -> int:
        if orgnr == "222222222":
            raise RuntimeError("Serper 500")
        return 4

    with (
        patch.object(
            news_refresh_monitor,
            "_companies_in_portfolios",
            return_value=["111111111", "222222222", "333333333"],
        ),
        patch.object(
            news_refresh_monitor, "refresh_company_news", side_effect=_refresh
        ),
    ):
        result = news_refresh_monitor.refresh_all_news(db)
    assert result["orgnrs_refreshed"] == 2
    assert result["orgnrs_failed"] == 1
    # 4 + 4 = 8 (the failing one contributed 0)
    assert result["articles_added"] == 8


def test_refresh_includes_timing_fields():
    """Cron operators need started_at/finished_at in the response to see
    if a run is taking abnormally long."""
    db = MagicMock()
    with patch.object(
        news_refresh_monitor, "_companies_in_portfolios", return_value=[]
    ):
        result = news_refresh_monitor.refresh_all_news(db)
    assert "started_at" in result
    assert "finished_at" in result
    assert result["started_at"] <= result["finished_at"]
