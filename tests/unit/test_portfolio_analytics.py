"""Unit tests for portfolio analytics — pure helpers + PortfolioService.get_analytics.

Pure static tests — uses MagicMock DB; no infrastructure required.
"""

from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock


from api.services.portfolio import PortfolioService, collect_alerts
from api.services.portfolio_analytics import (
    _insurer_concentration,
    _nace_section,
    _product_concentration,
    _rev_band,
)


def _mock_db():
    return MagicMock()


def _make_policy(insurer, product_type, premium, renewal_days=None):
    p = MagicMock()
    p.insurer = insurer
    p.product_type = product_type
    p.annual_premium_nok = premium
    p.renewal_date = (
        date.today() + timedelta(days=renewal_days)
        if renewal_days is not None
        else None
    )
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
    assert insurers[0] == "If"  # highest premium first
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


# ── _insurer_concentration (pure function) ───────────────────────────────────


def _pol(insurer, premium):
    p = MagicMock()
    p.insurer = insurer
    p.annual_premium_nok = premium
    return p


def test_insurer_concentration_groups_correctly():
    policies = [_pol("If", 100_000), _pol("If", 50_000), _pol("Gjensidige", 80_000)]
    result = _insurer_concentration(policies, 230_000)
    names = {r["insurer"] for r in result}
    assert names == {"If", "Gjensidige"}


def test_insurer_concentration_sums_premium_per_insurer():
    policies = [_pol("If", 60_000), _pol("If", 40_000)]
    result = _insurer_concentration(policies, 100_000)
    assert result[0]["premium_nok"] == 100_000


def test_insurer_concentration_counts_policies():
    policies = [_pol("If", 50_000), _pol("If", 50_000), _pol("If", 50_000)]
    result = _insurer_concentration(policies, 150_000)
    assert result[0]["policy_count"] == 3


def test_insurer_concentration_share_pct():
    policies = [_pol("A", 75_000), _pol("B", 25_000)]
    result = _insurer_concentration(policies, 100_000)
    a = next(r for r in result if r["insurer"] == "A")
    assert a["share_pct"] == 75.0


def test_insurer_concentration_sorted_desc():
    policies = [_pol("Small", 10_000), _pol("Large", 90_000)]
    result = _insurer_concentration(policies, 100_000)
    assert result[0]["insurer"] == "Large"


def test_insurer_concentration_none_insurer_becomes_ukjent():
    policies = [_pol(None, 50_000)]
    result = _insurer_concentration(policies, 50_000)
    assert result[0]["insurer"] == "Ukjent"


def test_insurer_concentration_zero_total_gives_zero_share():
    policies = [_pol("X", 0)]
    result = _insurer_concentration(policies, 0)
    assert result[0]["share_pct"] == 0


def test_insurer_concentration_empty_returns_empty():
    assert _insurer_concentration([], 0) == []


# ── _product_concentration (pure function) ───────────────────────────────────


def _prod_pol(product_type, premium):
    p = MagicMock()
    p.product_type = product_type
    p.annual_premium_nok = premium
    return p


def test_product_concentration_groups_correctly():
    policies = [
        _prod_pol("Ting", 100_000),
        _prod_pol("Ting", 50_000),
        _prod_pol("Ansvar", 80_000),
    ]
    result = _product_concentration(policies)
    types = {r["product_type"] for r in result}
    assert types == {"Ting", "Ansvar"}


def test_product_concentration_sums_premium():
    policies = [_prod_pol("Ting", 60_000), _prod_pol("Ting", 40_000)]
    result = _product_concentration(policies)
    assert result[0]["premium_nok"] == 100_000


def test_product_concentration_counts_correctly():
    policies = [_prod_pol("Cyber", 10_000) for _ in range(4)]
    result = _product_concentration(policies)
    assert result[0]["count"] == 4


def test_product_concentration_sorted_by_premium_desc():
    policies = [_prod_pol("Low", 10_000), _prod_pol("High", 90_000)]
    result = _product_concentration(policies)
    assert result[0]["product_type"] == "High"


def test_product_concentration_none_type_becomes_ukjent():
    policies = [_prod_pol(None, 50_000)]
    result = _product_concentration(policies)
    assert result[0]["product_type"] == "Ukjent"


def test_product_concentration_empty_returns_empty():
    assert _product_concentration([]) == []


# ── _rev_band (pure function) ────────────────────────────────────────────────


def test_rev_band_none_returns_ukjent():
    assert _rev_band(None) == "Ukjent"


def test_rev_band_zero_returns_ukjent():
    assert _rev_band(0) == "Ukjent"


def test_rev_band_small():
    assert _rev_band(5_000_000) == "<10 MNOK"


def test_rev_band_medium():
    assert _rev_band(50_000_000) == "10–100 MNOK"


def test_rev_band_large():
    assert _rev_band(500_000_000) == "100 MNOK–1 BNOK"


def test_rev_band_very_large():
    assert _rev_band(2_000_000_000) == ">1 BNOK"


def test_rev_band_boundary_10m():
    assert _rev_band(10_000_000) == "10–100 MNOK"


def test_rev_band_boundary_100m():
    assert _rev_band(100_000_000) == "100 MNOK–1 BNOK"


def test_rev_band_boundary_1bn():
    assert _rev_band(1_000_000_000) == ">1 BNOK"


# ── _nace_section (pure function) ────────────────────────────────────────────


def test_nace_section_none_returns_question_mark():
    assert _nace_section(None) == "?"


def test_nace_section_empty_string_returns_question_mark():
    assert _nace_section("") == "?"


def test_nace_section_code_1_maps_to_A():
    assert _nace_section("01.110") == "A"


def test_nace_section_integer_input():
    assert _nace_section(1) == "A"


def test_nace_section_unknown_code_returns_question_mark():
    assert _nace_section("999.99") == "?"


def test_nace_section_returns_single_letter():
    result = _nace_section("62.010")
    assert isinstance(result, str) and len(result) == 1


# ── collect_alerts (module-level function) ───────────────────────────────────


def _hist(year, revenue=None, equity_ratio=None, antall_ansatte=None):
    return SimpleNamespace(
        year=year,
        revenue=revenue,
        equity_ratio=equity_ratio,
        antall_ansatte=antall_ansatte,
    )


def _db_for_alerts(orgnrs, histories):
    db = MagicMock()
    pcs = [SimpleNamespace(orgnr=o) for o in orgnrs]
    companies = [SimpleNamespace(orgnr=o, navn=f"Co {o}") for o in orgnrs]
    db.query.return_value.filter.return_value.all.side_effect = [pcs, companies]
    # Batch history: flat list with orgnr injected (new non-N+1 implementation)
    all_hist = []
    for o in orgnrs:
        for h in histories.get(o, []):
            all_hist.append(
                SimpleNamespace(
                    orgnr=o,
                    year=h.year,
                    revenue=h.revenue,
                    equity_ratio=h.equity_ratio,
                    antall_ansatte=h.antall_ansatte,
                )
            )
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
        all_hist
    )
    return db


def test_collect_alerts_empty_when_no_history():
    db = _db_for_alerts(["123456789"], {"123456789": []})
    assert collect_alerts(1, db) == []


def test_collect_alerts_empty_with_single_year():
    db = _db_for_alerts(["123456789"], {"123456789": [_hist(2024, revenue=1_000_000)]})
    assert collect_alerts(1, db) == []


def test_collect_alerts_detects_strong_revenue_growth():
    db = _db_for_alerts(
        ["123456789"],
        {"123456789": [_hist(2024, revenue=1_300_000), _hist(2023, revenue=1_000_000)]},
    )
    result = collect_alerts(1, db)
    assert any(a["alert_type"] == "Sterk vekst" for a in result)


def test_collect_alerts_detects_revenue_fall():
    db = _db_for_alerts(
        ["123456789"],
        {"123456789": [_hist(2024, revenue=700_000), _hist(2023, revenue=1_000_000)]},
    )
    result = collect_alerts(1, db)
    assert any(a["alert_type"] == "Omsetningsfall" for a in result)


def test_collect_alerts_detects_negative_equity():
    db = _db_for_alerts(
        ["123456789"],
        {
            "123456789": [
                _hist(2024, equity_ratio=-0.05),
                _hist(2023, equity_ratio=0.30),
            ]
        },
    )
    result = collect_alerts(1, db)
    assert any(a["alert_type"] == "Negativ EK" for a in result)


def test_collect_alerts_detects_equity_drop():
    db = _db_for_alerts(
        ["123456789"],
        {"123456789": [_hist(2024, equity_ratio=0.20), _hist(2023, equity_ratio=0.30)]},
    )
    result = collect_alerts(1, db)
    assert any(a["alert_type"] == "Egenkapital svekket" for a in result)


def test_collect_alerts_detects_employee_growth():
    db = _db_for_alerts(
        ["123456789"],
        {"123456789": [_hist(2024, antall_ansatte=80), _hist(2023, antall_ansatte=50)]},
    )
    result = collect_alerts(1, db)
    assert any(a["alert_type"] == "Ny ansattvekst" for a in result)


def test_collect_alerts_detects_revenue_threshold_crossing():
    db = _db_for_alerts(
        ["123456789"],
        {
            "123456789": [
                _hist(2024, revenue=150_000_000),
                _hist(2023, revenue=80_000_000),
            ]
        },
    )
    result = collect_alerts(1, db)
    assert any(a["alert_type"] == "Krysset terskel" for a in result)


def test_collect_alerts_sorted_kritisk_before_hoy_before_moderat():
    db = _db_for_alerts(
        ["123456789"],
        {
            "123456789": [
                _hist(2024, revenue=700_000, equity_ratio=-0.05),
                _hist(2023, revenue=1_000_000, equity_ratio=0.30),
            ]
        },
    )
    result = collect_alerts(1, db)
    order = {"Kritisk": 0, "Høy": 1, "Moderat": 2}
    severities = [order[a["severity"]] for a in result]
    assert severities == sorted(severities)


def test_collect_alerts_no_false_positives_for_stable_company():
    db = _db_for_alerts(
        ["123456789"],
        {
            "123456789": [
                _hist(2024, revenue=1_050_000, equity_ratio=0.35, antall_ansatte=51),
                _hist(2023, revenue=1_000_000, equity_ratio=0.36, antall_ansatte=50),
            ]
        },
    )
    assert collect_alerts(1, db) == []
