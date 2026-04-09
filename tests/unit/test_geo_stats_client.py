"""Unit tests for api/services/geo_stats_client.py.

Covers Kartverket geocoding, SSB benchmarks (live + cached + fallback paths),
and Norges Bank exchange rate. Network is mocked at the requests level so
no SSB / Norges Bank API hits the wire.

The cache state in `_SSB_CACHE` and `_NB_RATE_CACHE` is module-global, so
each test that exercises a cache-aware code path resets the relevant dict
to avoid leaking state across tests.
"""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from api.services import geo_stats_client
from api.services.geo_stats_client import (
    _fetch_ssb_live,
    _nace_to_section,
    fetch_koordinater,
    fetch_norgesbank_rate,
    fetch_ssb_benchmark,
)


@pytest.fixture(autouse=True)
def _reset_caches():
    """Each test gets a clean SSB + Norges Bank cache."""
    geo_stats_client._SSB_CACHE.clear()
    geo_stats_client._NB_RATE_CACHE.clear()
    yield
    geo_stats_client._SSB_CACHE.clear()
    geo_stats_client._NB_RATE_CACHE.clear()


# ── fetch_koordinater ─────────────────────────────────────────────────────────

@patch("api.services.geo_stats_client.requests.get")
def test_fetch_koordinater_full(mock_get):
    mock_get.return_value = SimpleNamespace(
        status_code=200,
        json=lambda: {"adresser": [{
            "representasjonspunkt": {"lat": 59.9, "lon": 10.7},
            "adressetekst": "Storgata 1, 0150 OSLO",
        }]},
    )
    out = fetch_koordinater({
        "adresse": ["Storgata 1"], "postnummer": "0150", "kommunenummer": "0301",
    })
    assert out == {"lat": 59.9, "lon": 10.7, "adressetekst": "Storgata 1, 0150 OSLO"}


def test_fetch_koordinater_no_address():
    """Empty input returns None without hitting the network."""
    assert fetch_koordinater({}) is None
    assert fetch_koordinater({"adresse": [], "postnummer": "", "kommunenummer": ""}) is None


@patch("api.services.geo_stats_client.requests.get")
def test_fetch_koordinater_404(mock_get):
    mock_get.return_value = SimpleNamespace(status_code=404, json=lambda: {})
    assert fetch_koordinater({"adresse": ["Storgata 1"], "postnummer": "0150"}) is None


@patch("api.services.geo_stats_client.requests.get")
def test_fetch_koordinater_empty_results(mock_get):
    mock_get.return_value = SimpleNamespace(
        status_code=200, json=lambda: {"adresser": []},
    )
    assert fetch_koordinater({"adresse": ["Bogus"]}) is None


@patch("api.services.geo_stats_client.requests.get")
def test_fetch_koordinater_missing_lat_lon(mock_get):
    mock_get.return_value = SimpleNamespace(
        status_code=200,
        json=lambda: {"adresser": [{"representasjonspunkt": {"lat": None, "lon": None}}]},
    )
    assert fetch_koordinater({"adresse": ["X"]}) is None


@patch("api.services.geo_stats_client.requests.get", side_effect=Exception("network down"))
def test_fetch_koordinater_swallows_exceptions(mock_get):
    assert fetch_koordinater({"adresse": ["X"]}) is None


# ── _nace_to_section ──────────────────────────────────────────────────────────

def test_nace_to_section_known_codes():
    """64 (banking) → K, 62 (programming) → J, 71 (engineering) → M."""
    assert _nace_to_section("64.190") == "K"
    assert _nace_to_section("62.010") == "J"
    assert _nace_to_section("71.121") == "M"


def test_nace_to_section_invalid():
    assert _nace_to_section("") is None
    assert _nace_to_section("not-a-code") is None
    assert _nace_to_section(None) is None


def test_nace_to_section_out_of_range():
    """Division 999 isn't in any NACE section."""
    assert _nace_to_section("999.999") is None


# ── fetch_ssb_benchmark — fallback path (no live SSB) ─────────────────────────

@patch("api.services.geo_stats_client._fetch_ssb_live", return_value=None)
def test_fetch_ssb_benchmark_unknown_nace(mock_live):
    """Unknown NACE → None, never queries SSB."""
    assert fetch_ssb_benchmark("999.999") is None
    mock_live.assert_not_called()


@patch("api.services.geo_stats_client._fetch_ssb_live", return_value=None)
def test_fetch_ssb_benchmark_static_fallback(mock_live):
    """When live SSB returns None, the static NACE_BENCHMARKS table is used."""
    out = fetch_ssb_benchmark("64.190")
    assert out is not None
    assert out["section"] == "K"
    assert out["live"] is False
    assert out["typical_equity_ratio_min"] is not None


@patch("api.services.geo_stats_client._fetch_ssb_live")
def test_fetch_ssb_benchmark_live_success(mock_live):
    """When live SSB returns data, it overrides the static range."""
    mock_live.return_value = {
        "eq_ratio": 0.20, "margin": 0.05, "year": "2024", "table": "12813",
    }
    out = fetch_ssb_benchmark("64.190")
    assert out["live"] is True
    assert "live" in out["source"]
    assert "2024" in out["source"]
    # The live ratio should sit inside the new ±half-range
    assert out["typical_equity_ratio_min"] <= 0.20 <= out["typical_equity_ratio_max"]


# ── _fetch_ssb_live ───────────────────────────────────────────────────────────

@patch("api.services.geo_stats_client.requests.post")
def test_fetch_ssb_live_success(mock_post):
    mock_post.return_value = SimpleNamespace(
        ok=True,
        json=lambda: {
            "value": [12.5, 4.0],
            "dimension": {"Tid": {"category": {"label": {"a": "2024"}}}},
        },
    )
    out = _fetch_ssb_live("K")
    assert out is not None
    assert out["eq_ratio"] == 0.125
    assert out["margin"] == 0.04
    assert out["year"] == "2024"
    assert out["table"] == "12813"


@patch("api.services.geo_stats_client.requests.post")
def test_fetch_ssb_live_uses_cache(mock_post):
    """Second call within TTL skips the network."""
    mock_post.return_value = SimpleNamespace(
        ok=True,
        json=lambda: {"value": [10.0, 3.0],
                      "dimension": {"Tid": {"category": {"label": {"a": "2024"}}}}},
    )
    _fetch_ssb_live("K")
    _fetch_ssb_live("K")
    assert mock_post.call_count == 1


@patch("api.services.geo_stats_client.requests.post")
def test_fetch_ssb_live_falls_back_through_tables(mock_post):
    """If table 12813 fails, retries with table 12814."""
    mock_post.side_effect = [
        SimpleNamespace(ok=False),  # 12813 fails
        SimpleNamespace(ok=True, json=lambda: {
            "value": [11.0, 3.0],
            "dimension": {"Tid": {"category": {"label": {"a": "2024"}}}},
        }),
    ]
    out = _fetch_ssb_live("K")
    assert out is not None
    assert out["table"] == "12814"


@patch("api.services.geo_stats_client.requests.post")
def test_fetch_ssb_live_all_tables_fail(mock_post):
    mock_post.return_value = SimpleNamespace(ok=False)
    assert _fetch_ssb_live("K") is None


@patch("api.services.geo_stats_client.requests.post", side_effect=Exception("boom"))
def test_fetch_ssb_live_swallows_exceptions(mock_post):
    assert _fetch_ssb_live("K") is None


@patch("api.services.geo_stats_client.requests.post")
def test_fetch_ssb_live_value_with_none(mock_post):
    """Tables sometimes return [12.5, None] when one metric is missing — skip."""
    mock_post.return_value = SimpleNamespace(
        ok=True,
        json=lambda: {
            "value": [12.5, None],
            "dimension": {"Tid": {"category": {"label": {"a": "2024"}}}},
        },
    )
    # Both tables return the same broken shape
    assert _fetch_ssb_live("K") is None


# ── fetch_norgesbank_rate ─────────────────────────────────────────────────────

def test_norgesbank_rate_nok_is_one():
    """NOK → NOK is the trivial identity case, no network call."""
    assert fetch_norgesbank_rate("NOK") == 1.0
    assert fetch_norgesbank_rate("nok") == 1.0


def test_norgesbank_rate_empty_currency():
    assert fetch_norgesbank_rate("") == 1.0


@patch("api.services.geo_stats_client.requests.get")
def test_norgesbank_rate_eur(mock_get):
    mock_get.return_value = SimpleNamespace(
        ok=True,
        json=lambda: {"data": {"dataSets": [{"series": {
            "0:0:0": {"observations": {"0": [11.45]}}
        }}]}},
    )
    assert fetch_norgesbank_rate("EUR") == 11.45


@patch("api.services.geo_stats_client.requests.get")
def test_norgesbank_rate_uses_cache(mock_get):
    mock_get.return_value = SimpleNamespace(
        ok=True,
        json=lambda: {"data": {"dataSets": [{"series": {
            "0:0:0": {"observations": {"0": [11.45]}}
        }}]}},
    )
    fetch_norgesbank_rate("EUR")
    fetch_norgesbank_rate("EUR")
    assert mock_get.call_count == 1


@patch("api.services.geo_stats_client.requests.get", side_effect=Exception("boom"))
def test_norgesbank_rate_falls_back_to_one_on_failure(mock_get):
    assert fetch_norgesbank_rate("EUR") == 1.0


@patch("api.services.geo_stats_client.requests.get")
def test_norgesbank_rate_not_ok_returns_one(mock_get):
    mock_get.return_value = SimpleNamespace(ok=False)
    assert fetch_norgesbank_rate("EUR") == 1.0
