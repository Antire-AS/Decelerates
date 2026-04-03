"""Unit tests for api/routers/utils.py — org-enrichment endpoints."""
import sys
from unittest.mock import MagicMock, patch

import pytest
import requests as _requests
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.routers.utils import router

_app = FastAPI()
_app.include_router(router)

# utils.py has no DB dependency, so no fixture needed
client = TestClient(_app)


# ── GET /org/{orgnr}/roles ────────────────────────────────────────────────────

def test_get_org_roles_returns_members():
    members = [{"name": "Ola Nordmann", "role": "Styreformann"}]
    with patch("api.routers.utils.fetch_board_members", return_value=members):
        resp = client.get("/org/123456789/roles")
    assert resp.status_code == 200
    assert resp.json()["members"] == members
    assert resp.json()["orgnr"] == "123456789"


def test_get_org_roles_returns_502_on_http_error():
    with patch("api.routers.utils.fetch_board_members",
               side_effect=_requests.HTTPError("upstream")):
        resp = client.get("/org/123456789/roles")
    assert resp.status_code == 502


# ── GET /org/{orgnr}/estimate ─────────────────────────────────────────────────

def test_get_synthetic_estimate_returns_200():
    org = {"orgnr": "123456789", "navn": "Test AS"}
    estimated = {"revenue": "10M NOK", "equity": "2M NOK"}
    with patch("api.routers.utils.fetch_enhet_by_orgnr", return_value=org), \
         patch("api.routers.utils._generate_synthetic_financials", return_value=estimated):
        resp = client.get("/org/123456789/estimate")
    assert resp.status_code == 200
    assert resp.json()["estimated"] == estimated


def test_get_synthetic_estimate_returns_404_when_not_found():
    with patch("api.routers.utils.fetch_enhet_by_orgnr", return_value=None):
        resp = client.get("/org/123456789/estimate")
    assert resp.status_code == 404


def test_get_synthetic_estimate_returns_503_when_llm_fails():
    org = {"orgnr": "123456789"}
    with patch("api.routers.utils.fetch_enhet_by_orgnr", return_value=org), \
         patch("api.routers.utils._generate_synthetic_financials", return_value=None):
        resp = client.get("/org/123456789/estimate")
    assert resp.status_code == 503


# ── GET /org/{orgnr}/bankruptcy ───────────────────────────────────────────────

def test_get_bankruptcy_returns_status_flags():
    org = {"konkurs": False, "under_konkursbehandling": True, "under_avvikling": False}
    with patch("api.routers.utils.fetch_enhet_by_orgnr", return_value=org):
        resp = client.get("/org/123456789/bankruptcy")
    assert resp.status_code == 200
    body = resp.json()
    assert body["konkurs"] is False
    assert body["under_konkursbehandling"] is True


def test_get_bankruptcy_returns_404_when_not_found():
    with patch("api.routers.utils.fetch_enhet_by_orgnr", return_value=None):
        resp = client.get("/org/123456789/bankruptcy")
    assert resp.status_code == 404


# ── GET /org/{orgnr}/koordinater ──────────────────────────────────────────────

def test_get_koordinater_returns_coordinates():
    org = {"navn": "Test AS", "forretningsadresse": {}}
    coords = {"lat": 59.91, "lon": 10.75}
    with patch("api.routers.utils.fetch_enhet_by_orgnr", return_value=org), \
         patch("api.routers.utils.fetch_koordinater", return_value=coords):
        resp = client.get("/org/123456789/koordinater")
    assert resp.status_code == 200
    assert resp.json()["coordinates"] == coords


def test_get_koordinater_returns_404_when_not_found():
    with patch("api.routers.utils.fetch_enhet_by_orgnr", return_value=None):
        resp = client.get("/org/123456789/koordinater")
    assert resp.status_code == 404


# ── GET /org/{orgnr}/losore ───────────────────────────────────────────────────

def test_get_losore_returns_result():
    with patch("api.routers.utils.fetch_losore",
               return_value={"auth_required": False, "items": []}):
        resp = client.get("/org/123456789/losore")
    assert resp.status_code == 200
    assert resp.json()["orgnr"] == "123456789"
    assert resp.json()["auth_required"] is False


# ── GET /org/{orgnr}/benchmark ────────────────────────────────────────────────

def test_get_benchmark_returns_nace_and_benchmark():
    org = {"naeringskode1": "41.200"}
    benchmark = {"equity_ratio_low": 0.1, "equity_ratio_high": 0.4}
    with patch("api.routers.utils.fetch_enhet_by_orgnr", return_value=org), \
         patch("api.routers.utils.fetch_ssb_benchmark", return_value=benchmark):
        resp = client.get("/org/123456789/benchmark")
    assert resp.status_code == 200
    body = resp.json()
    assert body["nace_code"] == "41.200"
    assert body["benchmark"] == benchmark


def test_get_benchmark_returns_404_when_not_found():
    with patch("api.routers.utils.fetch_enhet_by_orgnr", return_value=None):
        resp = client.get("/org/123456789/benchmark")
    assert resp.status_code == 404


# ── GET /org/{orgnr}/struktur ─────────────────────────────────────────────────

def test_get_company_struktur_returns_structure():
    with patch("api.routers.utils.fetch_company_struktur",
               return_value={"parent": None, "sub_units": []}):
        resp = client.get("/org/123456789/struktur")
    assert resp.status_code == 200
    assert resp.json()["orgnr"] == "123456789"
    assert resp.json()["sub_units"] == []


# ── GET /norgesbank/rate/{currency} ───────────────────────────────────────────

def test_get_norgesbank_rate_returns_rate():
    with patch("api.routers.utils.fetch_norgesbank_rate", return_value=10.5):
        resp = client.get("/norgesbank/rate/EUR")
    assert resp.status_code == 200
    body = resp.json()
    assert body["currency"] == "EUR"
    assert body["nok_rate"] == 10.5
    assert "Norges Bank" in body["source"]


def test_get_norgesbank_rate_uppercases_currency():
    with patch("api.routers.utils.fetch_norgesbank_rate", return_value=None) as mock_fn:
        client.get("/norgesbank/rate/usd")
    mock_fn.assert_called_once_with("USD")
