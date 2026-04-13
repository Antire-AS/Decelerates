"""Unit tests for api/services/risk_monitor.py — weekly BRREG refresh + risk alerts."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from api.services.risk_monitor import (
    _fetch_brreg_data,
    _notify_risk_changes,
    _refresh_company,
    _update_company_fields,
    refresh_all_portfolios,
)


# ── _fetch_brreg_data ─────────────────────────────────────────────────────────

@patch("api.services.brreg_client.fetch_regnskap_keyfigures", return_value={"rev": 100})
@patch("api.services.brreg_client.fetch_enhet_by_orgnr", return_value={"navn": "Test"})
def test_fetch_brreg_success(mock_enhet, mock_regn):
    result = _fetch_brreg_data("123")
    assert result is not None
    org, regn = result
    assert org["navn"] == "Test"
    assert regn["rev"] == 100


@patch("api.services.brreg_client.fetch_enhet_by_orgnr", side_effect=Exception("timeout"))
def test_fetch_brreg_failure(mock_enhet):
    assert _fetch_brreg_data("123") is None


# ── _update_company_fields ────────────────────────────────────────────────────

def test_update_company_fields():
    company = SimpleNamespace(
        risk_score=None, equity_ratio=None,
        sum_driftsinntekter=None, sum_egenkapital=None,
        sum_eiendeler=None, last_refreshed_at=None,
    )
    regn = {"sum_driftsinntekter": 100, "sum_egenkapital": 40, "sum_eiendeler": 200}
    _update_company_fields(company, regn, 7, 0.2)
    assert company.risk_score == 7
    assert company.equity_ratio == 0.2
    assert company.sum_driftsinntekter == 100
    assert company.last_refreshed_at is not None


def test_update_company_fields_skips_none_regn():
    company = SimpleNamespace(
        risk_score=5, equity_ratio=0.3,
        sum_driftsinntekter=50, sum_egenkapital=20,
        sum_eiendeler=100, last_refreshed_at=None,
    )
    _update_company_fields(company, {}, 6, 0.25)
    assert company.risk_score == 6
    assert company.sum_driftsinntekter == 50  # unchanged


# ── _refresh_company ──────────────────────────────────────────────────────────

@patch("api.risk.derive_simple_risk")
@patch("api.services.risk_monitor._fetch_brreg_data")
def test_refresh_company_detects_change(mock_brreg, mock_risk):
    db = MagicMock()
    company = SimpleNamespace(
        orgnr="123", navn="Test AS", risk_score=3,
        equity_ratio=0.2, sum_driftsinntekter=100,
        sum_egenkapital=40, sum_eiendeler=200, last_refreshed_at=None,
    )
    db.query.return_value.filter.return_value.first.return_value = company
    mock_brreg.return_value = ({"navn": "Test AS"}, {"sum_driftsinntekter": 120})
    mock_risk.return_value = {"score": 8, "equity_ratio": 0.15}

    change = _refresh_company("123", db)
    assert change is not None
    assert change["old_score"] == 3
    assert change["new_score"] == 8
    assert change["change"] == 5


@patch("api.risk.derive_simple_risk")
@patch("api.services.risk_monitor._fetch_brreg_data")
def test_refresh_company_no_significant_change(mock_brreg, mock_risk):
    db = MagicMock()
    company = SimpleNamespace(
        orgnr="123", navn="Test AS", risk_score=5,
        equity_ratio=0.2, sum_driftsinntekter=100,
        sum_egenkapital=40, sum_eiendeler=200, last_refreshed_at=None,
    )
    db.query.return_value.filter.return_value.first.return_value = company
    mock_brreg.return_value = ({}, {})
    mock_risk.return_value = {"score": 6, "equity_ratio": 0.19}

    change = _refresh_company("123", db)
    assert change is None  # only 1 point change, under threshold


@patch("api.services.risk_monitor._fetch_brreg_data", return_value=None)
def test_refresh_company_brreg_failure(mock_brreg):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
        orgnr="123", risk_score=5)
    assert _refresh_company("123", db) is None


def test_refresh_company_not_found():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    assert _refresh_company("000", db) is None


# ── _notify_risk_changes ──────────────────────────────────────────────────────

@patch("api.services.notification_inbox_service.create_notification_for_users_safe")
def test_notify_creates_notifications(mock_notify):
    db = MagicMock()
    changes = [
        {"orgnr": "123", "navn": "Test AS", "old_score": 3, "new_score": 8},
        {"orgnr": "456", "navn": "Other AS", "old_score": 10, "new_score": 5},
    ]
    _notify_risk_changes(changes, 1, db)
    assert mock_notify.call_count == 2
    # First call: score increased
    first_call = mock_notify.call_args_list[0]
    assert "økt" in first_call.kwargs.get("message", "") or "økt" in str(first_call)
    # Second call: score decreased
    second_call = mock_notify.call_args_list[1]
    assert "redusert" in second_call.kwargs.get("message", "") or "redusert" in str(second_call)


# ── refresh_all_portfolios ────────────────────────────────────────────────────

@patch("api.services.risk_monitor._notify_risk_changes")
@patch("api.services.risk_monitor._refresh_company")
@patch("api.services.risk_monitor.time.sleep")  # skip delays in tests
def test_refresh_all_portfolios(mock_sleep, mock_refresh, mock_notify):
    db = MagicMock()
    pc1 = SimpleNamespace(orgnr="123")
    pc2 = SimpleNamespace(orgnr="456")
    db.query.return_value.distinct.return_value.all.return_value = [pc1, pc2]
    mock_refresh.side_effect = [
        {"orgnr": "123", "navn": "X", "old_score": 3, "new_score": 8, "change": 5},
        None,
    ]
    result = refresh_all_portfolios(1, db)
    assert result["companies_refreshed"] == 2
    assert result["total_changes"] == 1
    assert len(result["risk_changes"]) == 1
    db.commit.assert_called_once()
