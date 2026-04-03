"""Unit tests for api/services/portfolio.py — PortfolioService + collect_alerts.

Pure static tests — uses MagicMock DB; no infrastructure required.
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from api.db import Company, CompanyHistory, Portfolio, PortfolioCompany
from api.domain.exceptions import NotFoundError
from api.services.portfolio import PortfolioService, collect_alerts


# ── helpers ───────────────────────────────────────────────────────────────────

def _mock_db():
    return MagicMock()


def _mock_portfolio(**kwargs):
    p = MagicMock(spec=Portfolio)
    p.id      = kwargs.get("id", 1)
    p.name    = kwargs.get("name", "Test Portfolio")
    p.firm_id = kwargs.get("firm_id", 10)
    return p


def _mock_pc(**kwargs):
    pc = MagicMock(spec=PortfolioCompany)
    pc.portfolio_id = kwargs.get("portfolio_id", 1)
    pc.orgnr        = kwargs.get("orgnr", "123456789")
    pc.added_at     = kwargs.get("added_at", "2026-01-01T00:00:00+00:00")
    return pc


def _mock_company(**kwargs):
    c = MagicMock(spec=Company)
    c.orgnr                       = kwargs.get("orgnr", "123456789")
    c.navn                        = kwargs.get("navn", "Test AS")
    c.kommune                     = kwargs.get("kommune", "Oslo")
    c.naeringskode1_beskrivelse   = kwargs.get("naeringskode1_beskrivelse", "IT-tjenester")
    c.naeringskode1               = kwargs.get("naeringskode1", "62.010")
    c.risk_score                  = kwargs.get("risk_score", 3)
    c.regnskapsår                 = kwargs.get("regnskapsår", 2024)
    c.sum_driftsinntekter         = kwargs.get("sum_driftsinntekter", 5_000_000)
    c.sum_egenkapital             = kwargs.get("sum_egenkapital", 2_000_000)
    c.equity_ratio                = kwargs.get("equity_ratio", 0.4)
    return c


def _mock_hist(**kwargs):
    h = MagicMock(spec=CompanyHistory)
    h.orgnr       = kwargs.get("orgnr", "123456789")
    h.year        = kwargs.get("year", 2024)
    h.revenue     = kwargs.get("revenue", 10_000_000)
    h.equity      = kwargs.get("equity", 4_000_000)
    h.equity_ratio = kwargs.get("equity_ratio", 0.4)
    h.antall_ansatte = kwargs.get("antall_ansatte", 50)
    return h


# ── create ────────────────────────────────────────────────────────────────────

def test_create_adds_to_db_and_commits():
    db = _mock_db()
    PortfolioService(db).create("My Portfolio", 10)
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_create_strips_name_whitespace():
    db = _mock_db()
    PortfolioService(db).create("  My Portfolio  ", 10)
    added = db.add.call_args[0][0]
    assert added.name == "My Portfolio"


def test_create_sets_firm_id():
    db = _mock_db()
    PortfolioService(db).create("Portfolio", 42)
    added = db.add.call_args[0][0]
    assert added.firm_id == 42


def test_create_strips_description():
    db = _mock_db()
    PortfolioService(db).create("Portfolio", 10, "  Some desc  ")
    added = db.add.call_args[0][0]
    assert added.description == "Some desc"


def test_create_sets_created_at():
    db = _mock_db()
    PortfolioService(db).create("Portfolio", 10)
    added = db.add.call_args[0][0]
    assert added.created_at is not None


def test_create_returns_portfolio():
    db = _mock_db()
    result = PortfolioService(db).create("Portfolio", 10)
    assert result is db.add.call_args[0][0]


# ── list_portfolios ───────────────────────────────────────────────────────────

def test_list_portfolios_returns_results():
    portfolios = [_mock_portfolio(), _mock_portfolio(id=2)]
    db = _mock_db()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = portfolios
    result = PortfolioService(db).list_portfolios(10)
    assert result == portfolios


def test_list_portfolios_returns_empty_when_none():
    db = _mock_db()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    result = PortfolioService(db).list_portfolios(99)
    assert result == []


# ── get ───────────────────────────────────────────────────────────────────────

def test_get_returns_portfolio_when_found():
    portfolio = _mock_portfolio()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = portfolio
    result = PortfolioService(db).get(1)
    assert result is portfolio


def test_get_raises_not_found_when_missing():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(NotFoundError, match="Portfolio 99 not found"):
        PortfolioService(db).get(99)


def test_get_with_firm_id_applies_additional_filter():
    portfolio = _mock_portfolio()
    db = _mock_db()
    # Chained filter calls — both filters applied
    db.query.return_value.filter.return_value.filter.return_value.first.return_value = portfolio
    result = PortfolioService(db).get(1, firm_id=10)
    assert result is portfolio


# ── delete ────────────────────────────────────────────────────────────────────

def test_delete_removes_portfolio_and_commits():
    portfolio = _mock_portfolio()
    db = _mock_db()
    # delete() → get(id, firm_id) → .filter().filter().first()
    db.query.return_value.filter.return_value.filter.return_value.first.return_value = portfolio
    PortfolioService(db).delete(1, 10)
    db.delete.assert_called_once_with(portfolio)
    db.commit.assert_called_once()


def test_delete_raises_not_found_when_missing():
    db = _mock_db()
    db.query.return_value.filter.return_value.filter.return_value.first.return_value = None
    with pytest.raises(NotFoundError):
        PortfolioService(db).delete(999, 10)


# ── add_company ───────────────────────────────────────────────────────────────

def test_add_company_adds_when_not_existing():
    db = _mock_db()
    # get() → portfolio found; existing check → None
    db.query.return_value.filter.return_value.first.side_effect = [
        _mock_portfolio(), None
    ]
    PortfolioService(db).add_company(1, "123456789")
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_add_company_skips_when_already_member():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.side_effect = [
        _mock_portfolio(), _mock_pc()
    ]
    PortfolioService(db).add_company(1, "123456789")
    db.add.assert_not_called()


def test_add_company_raises_not_found_for_missing_portfolio():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(NotFoundError):
        PortfolioService(db).add_company(999, "123456789")


def test_add_company_sets_orgnr():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.side_effect = [
        _mock_portfolio(), None
    ]
    PortfolioService(db).add_company(1, "987654321")
    added = db.add.call_args[0][0]
    assert added.orgnr == "987654321"


# ── remove_company ────────────────────────────────────────────────────────────

def test_remove_company_deletes_when_found():
    pc = _mock_pc()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = pc
    PortfolioService(db).remove_company(1, "123456789")
    db.delete.assert_called_once_with(pc)
    db.commit.assert_called_once()


def test_remove_company_is_noop_when_not_member():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    PortfolioService(db).remove_company(1, "000000000")
    db.delete.assert_not_called()
    db.commit.assert_not_called()


# ── get_risk_summary ──────────────────────────────────────────────────────────

def _db_for_risk_summary(pc_list, company=None, hist=None):
    """Return a mock DB wired for get_risk_summary batch queries.

    get_risk_summary now uses 3 queries:
      1. PortfolioCompany: .filter().all()       → pc_list
      2. Company: .filter().all()                → company_list (batch)
      3. CompanyHistory subquery + join: via _fetch_latest_hist_map
    """
    company_list = [company] if company else []
    hist_list = [hist] if hist else []

    def _query(*args):
        m = MagicMock()
        first = args[0] if args else None
        if first is PortfolioCompany:
            m.filter.return_value.all.return_value = pc_list
        elif first is Company:
            m.filter.return_value.all.return_value = company_list
        elif first is CompanyHistory:
            m.join.return_value.all.return_value = hist_list
        else:
            # subquery: .filter().group_by().subquery()
            m.filter.return_value.group_by.return_value.subquery.return_value = MagicMock()
        return m

    db = _mock_db()
    db.query.side_effect = _query
    return db


def test_get_risk_summary_returns_list():
    pc = _mock_pc()
    company = _mock_company()
    hist = _mock_hist()
    db = _db_for_risk_summary([pc], company, hist)
    result = PortfolioService(db).get_risk_summary(1)
    assert isinstance(result, list)
    assert len(result) == 1


def test_get_risk_summary_includes_orgnr():
    pc = _mock_pc(orgnr="123456789")
    company = _mock_company(orgnr="123456789")
    db = _db_for_risk_summary([pc], company, None)
    result = PortfolioService(db).get_risk_summary(1)
    assert result[0]["orgnr"] == "123456789"


def test_get_risk_summary_uses_company_name():
    pc = _mock_pc()
    company = _mock_company(navn="DNB Bank ASA")
    db = _db_for_risk_summary([pc], company, None)
    result = PortfolioService(db).get_risk_summary(1)
    assert result[0]["navn"] == "DNB Bank ASA"


def test_get_risk_summary_falls_back_to_orgnr_when_no_company():
    pc = _mock_pc(orgnr="123456789")
    db = _db_for_risk_summary([pc], company=None, hist=None)
    db.query.return_value.filter.return_value.first.return_value = None
    result = PortfolioService(db).get_risk_summary(1)
    assert result[0]["orgnr"] == "123456789"
    assert result[0]["navn"] == "123456789"


def test_get_risk_summary_prefers_hist_revenue_over_company():
    pc = _mock_pc()
    company = _mock_company(sum_driftsinntekter=1_000_000)
    hist = _mock_hist(revenue=9_999_999)
    db = _db_for_risk_summary([pc], company, hist)
    result = PortfolioService(db).get_risk_summary(1)
    assert result[0]["revenue"] == 9_999_999


def test_get_risk_summary_sorted_by_risk_score_desc():
    pc1 = _mock_pc(orgnr="111111111")
    pc2 = _mock_pc(orgnr="222222222")
    c1 = _mock_company(orgnr="111111111", risk_score=2)
    c2 = _mock_company(orgnr="222222222", risk_score=5)

    def _query(*args):
        m = MagicMock()
        first = args[0] if args else None
        if first is PortfolioCompany:
            m.filter.return_value.all.return_value = [pc1, pc2]
        elif first is Company:
            m.filter.return_value.all.return_value = [c1, c2]
        elif first is CompanyHistory:
            m.join.return_value.all.return_value = []
        else:
            m.filter.return_value.group_by.return_value.subquery.return_value = MagicMock()
        return m

    db = _mock_db()
    db.query.side_effect = _query
    result = PortfolioService(db).get_risk_summary(1)
    assert result[0]["risk_score"] == 5


def test_get_risk_summary_empty_portfolio():
    db = _mock_db()
    db.query.return_value.filter.return_value.all.return_value = []
    result = PortfolioService(db).get_risk_summary(1)
    assert result == []


# ── collect_alerts ────────────────────────────────────────────────────────────

def _db_for_alerts(orgnrs, histories_by_orgnr, companies=None):
    db = _mock_db()
    pcs = [_mock_pc(orgnr=o) for o in orgnrs]
    db.query.return_value.filter.return_value.all.side_effect = [
        pcs,
        companies or [_mock_company(orgnr=o, navn=f"Co {o}") for o in orgnrs],
    ]
    # Batch history: flat list with orgnr injected (new non-N+1 implementation)
    all_hist = []
    for o in orgnrs:
        for h in histories_by_orgnr.get(o, []):
            all_hist.append(SimpleNamespace(
                orgnr=o, year=h.year, revenue=h.revenue,
                equity_ratio=h.equity_ratio, antall_ansatte=h.antall_ansatte,
            ))
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = all_hist
    return db


def _make_hist(year, revenue=None, equity_ratio=None, antall_ansatte=None):
    h = SimpleNamespace(year=year, revenue=revenue, equity_ratio=equity_ratio,
                        antall_ansatte=antall_ansatte)
    return h


def test_collect_alerts_returns_empty_when_no_history():
    db = _db_for_alerts(["123456789"], {"123456789": []})
    result = collect_alerts(1, db)
    assert result == []


def test_collect_alerts_returns_empty_with_single_year():
    hist = [_make_hist(2024, revenue=1_000_000)]
    db = _db_for_alerts(["123456789"], {"123456789": hist})
    result = collect_alerts(1, db)
    assert result == []


def test_collect_alerts_detects_revenue_growth_above_25pct():
    hist = [
        _make_hist(2024, revenue=1_300_000),
        _make_hist(2023, revenue=1_000_000),
    ]
    db = _db_for_alerts(["123456789"], {"123456789": hist})
    result = collect_alerts(1, db)
    assert any(a["alert_type"] == "Sterk vekst" for a in result)


def test_collect_alerts_detects_revenue_fall_below_minus20pct():
    hist = [
        _make_hist(2024, revenue=700_000),
        _make_hist(2023, revenue=1_000_000),
    ]
    db = _db_for_alerts(["123456789"], {"123456789": hist})
    result = collect_alerts(1, db)
    assert any(a["alert_type"] == "Omsetningsfall" for a in result)


def test_collect_alerts_detects_negative_equity():
    hist = [
        _make_hist(2024, equity_ratio=-0.05),
        _make_hist(2023, equity_ratio=0.30),
    ]
    db = _db_for_alerts(["123456789"], {"123456789": hist})
    result = collect_alerts(1, db)
    assert any(a["alert_type"] == "Negativ EK" for a in result)


def test_collect_alerts_detects_equity_drop_above_8pp():
    hist = [
        _make_hist(2024, equity_ratio=0.20),
        _make_hist(2023, equity_ratio=0.30),
    ]
    db = _db_for_alerts(["123456789"], {"123456789": hist})
    result = collect_alerts(1, db)
    assert any(a["alert_type"] == "Egenkapital svekket" for a in result)


def test_collect_alerts_detects_employee_growth_above_50pct():
    hist = [
        _make_hist(2024, antall_ansatte=80),
        _make_hist(2023, antall_ansatte=50),
    ]
    db = _db_for_alerts(["123456789"], {"123456789": hist})
    result = collect_alerts(1, db)
    assert any(a["alert_type"] == "Ny ansattvekst" for a in result)


def test_collect_alerts_detects_revenue_threshold_crossing():
    hist = [
        _make_hist(2024, revenue=150_000_000),
        _make_hist(2023, revenue=80_000_000),
    ]
    db = _db_for_alerts(["123456789"], {"123456789": hist})
    result = collect_alerts(1, db)
    assert any(a["alert_type"] == "Krysset terskel" for a in result)


def test_collect_alerts_sorted_kritisk_first():
    hist = [
        _make_hist(2024, revenue=700_000, equity_ratio=-0.05),
        _make_hist(2023, revenue=1_000_000, equity_ratio=0.30),
    ]
    db = _db_for_alerts(["123456789"], {"123456789": hist})
    result = collect_alerts(1, db)
    severities = [a["severity"] for a in result]
    assert severities == sorted(severities, key=lambda s: {"Kritisk": 0, "Høy": 1, "Moderat": 2}[s])


def test_collect_alerts_no_false_positive_for_stable_company():
    hist = [
        _make_hist(2024, revenue=1_050_000, equity_ratio=0.35, antall_ansatte=51),
        _make_hist(2023, revenue=1_000_000, equity_ratio=0.36, antall_ansatte=50),
    ]
    db = _db_for_alerts(["123456789"], {"123456789": hist})
    result = collect_alerts(1, db)
    assert result == []
