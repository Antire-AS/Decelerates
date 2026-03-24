"""Unit tests for PortfolioService.get_analytics — premium aggregation logic.

Pure static tests — uses MagicMock DB; no infrastructure required.
"""
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from api.services.portfolio import PortfolioService


def _mock_db():
    return MagicMock()


def _make_policy(insurer, product_type, premium, renewal_days=None):
    p = MagicMock()
    p.insurer = insurer
    p.product_type = product_type
    p.annual_premium_nok = premium
    p.renewal_date = date.today() + timedelta(days=renewal_days) if renewal_days is not None else None
    return p


def _make_portfolio_company(orgnr):
    pc = MagicMock()
    pc.orgnr = orgnr
    return pc


def _svc_with_policies(portfolio_companies, policies):
    db = _mock_db()
    # PortfolioService.get() returns a mock portfolio
    mock_portfolio = MagicMock()
    # First query call: PortfolioCompany rows
    # Second query call: Policy rows
    db.query.return_value.filter.return_value.first.return_value = mock_portfolio
    db.query.return_value.filter.return_value.all.side_effect = [
        portfolio_companies,
        policies,
    ]
    return PortfolioService(db)


# ── Empty portfolio ───────────────────────────────────────────────────────────

def test_analytics_empty_portfolio_returns_zeros():
    db = _mock_db()
    mock_portfolio = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = mock_portfolio
    db.query.return_value.filter.return_value.all.return_value = []
    svc = PortfolioService(db)
    result = svc.get_analytics(1, firm_id=1)
    assert result["active_policy_count"] == 0
    assert result["total_annual_premium_nok"] == 0
    assert result["insurer_concentration"] == []


# ── Premium totals ────────────────────────────────────────────────────────────

def test_analytics_sums_premium_correctly():
    pcs = [_make_portfolio_company("111111111"), _make_portfolio_company("222222222")]
    policies = [
        _make_policy("If", "Ting", 100_000),
        _make_policy("If", "Ansvar", 200_000),
        _make_policy("Gjensidige", "Cyber", 50_000),
    ]
    svc = _svc_with_policies(pcs, policies)
    result = svc.get_analytics(1, firm_id=1)
    assert result["total_annual_premium_nok"] == 350_000
    assert result["active_policy_count"] == 3


# ── Insurer concentration ─────────────────────────────────────────────────────

def test_analytics_insurer_concentration_sorted_by_premium():
    pcs = [_make_portfolio_company("111111111")]
    policies = [
        _make_policy("Gjensidige", "Ting", 50_000),
        _make_policy("If", "Ting", 200_000),
        _make_policy("If", "Ansvar", 100_000),
    ]
    svc = _svc_with_policies(pcs, policies)
    result = svc.get_analytics(1, firm_id=1)
    insurers = [r["insurer"] for r in result["insurer_concentration"]]
    assert insurers[0] == "If"   # highest premium first
    assert insurers[1] == "Gjensidige"


def test_analytics_insurer_share_pct_sums_to_100():
    pcs = [_make_portfolio_company("111111111")]
    policies = [
        _make_policy("If", "Ting", 300_000),
        _make_policy("Gjensidige", "Cyber", 100_000),
        _make_policy("Storebrand", "Ansvar", 100_000),
    ]
    svc = _svc_with_policies(pcs, policies)
    result = svc.get_analytics(1, firm_id=1)
    total_share = sum(r["share_pct"] for r in result["insurer_concentration"])
    assert abs(total_share - 100.0) < 0.2  # allow rounding


# ── Upcoming renewals ─────────────────────────────────────────────────────────

def test_analytics_counts_renewals_within_90_days():
    pcs = [_make_portfolio_company("111111111")]
    policies = [
        _make_policy("If", "Ting", 100_000, renewal_days=30),
        _make_policy("If", "Ansvar", 100_000, renewal_days=60),
        _make_policy("If", "Cyber", 100_000, renewal_days=120),  # outside 90d
    ]
    svc = _svc_with_policies(pcs, policies)
    result = svc.get_analytics(1, firm_id=1)
    assert result["upcoming_renewals_90d"] == 2


def test_analytics_counts_renewals_within_30_days():
    pcs = [_make_portfolio_company("111111111")]
    policies = [
        _make_policy("If", "Ting", 100_000, renewal_days=15),
        _make_policy("If", "Ansvar", 100_000, renewal_days=60),
    ]
    svc = _svc_with_policies(pcs, policies)
    result = svc.get_analytics(1, firm_id=1)
    assert result["upcoming_renewals_30d"] == 1


def test_analytics_no_renewals_when_no_renewal_date():
    pcs = [_make_portfolio_company("111111111")]
    policies = [_make_policy("If", "Ting", 100_000, renewal_days=None)]
    svc = _svc_with_policies(pcs, policies)
    result = svc.get_analytics(1, firm_id=1)
    assert result["upcoming_renewals_90d"] == 0
