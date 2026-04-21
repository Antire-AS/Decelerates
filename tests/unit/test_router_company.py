"""Unit tests for api/routers/company.py — ping, search, org profile, licenses, companies."""

import sys
from unittest.mock import MagicMock, patch

import pytest
import requests as _requests
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.routers.company import router
from api.dependencies import get_db
from api.limiter import limiter

_app = FastAPI()
_app.state.limiter = limiter
_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
_app.include_router(router)


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def client(mock_db):
    _app.dependency_overrides[get_db] = lambda: mock_db
    yield TestClient(_app)
    _app.dependency_overrides.clear()


# ── GET /ping ─────────────────────────────────────────────────────────────────


def test_ping_returns_ok(client):
    resp = client.get("/ping")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ── GET /search ───────────────────────────────────────────────────────────────


def test_search_returns_results(client):
    results = [{"orgnr": "123456789", "navn": "Test AS"}]
    with patch("api.routers.company.fetch_enhetsregisteret", return_value=results):
        resp = client.get("/search?name=Test")
    assert resp.status_code == 200
    assert resp.json() == results


def test_search_returns_empty_list(client):
    with patch("api.routers.company.fetch_enhetsregisteret", return_value=[]):
        resp = client.get("/search?name=NoMatch")
    assert resp.json() == []


def test_search_returns_502_on_http_error(client):
    with patch(
        "api.routers.company.fetch_enhetsregisteret",
        side_effect=_requests.HTTPError("upstream error"),
    ):
        resp = client.get("/search?name=Fail")
    assert resp.status_code == 502


def test_search_rejects_single_char_name(client):
    resp = client.get("/search?name=X")
    assert resp.status_code == 422


# ── GET /org/{orgnr} ──────────────────────────────────────────────────────────


def test_get_org_profile_returns_200(client):
    profile = {"org": {"orgnr": "123456789", "navn": "Test AS"}, "risk": {}}
    with (
        patch("api.routers.company.fetch_org_profile", return_value=profile),
        patch("api.routers.company.log_audit"),
        patch("api.routers.company.JobQueueService"),
    ):
        resp = client.get("/org/123456789")
    assert resp.status_code == 200
    assert resp.json()["org"]["orgnr"] == "123456789"


def test_get_org_profile_returns_404_when_none(client):
    with (
        patch("api.routers.company.fetch_org_profile", return_value=None),
        patch("api.routers.company.log_audit"),
        patch("api.routers.company.JobQueueService"),
    ):
        resp = client.get("/org/999999999")
    assert resp.status_code == 404


def test_get_org_profile_returns_502_on_http_error(client):
    with (
        patch(
            "api.routers.company.fetch_org_profile",
            side_effect=_requests.HTTPError("bad gateway"),
        ),
        patch("api.routers.company.log_audit"),
        patch("api.routers.company.JobQueueService"),
    ):
        resp = client.get("/org/123456789")
    assert resp.status_code == 502


def test_get_org_profile_enqueues_pdf_extract(client):
    profile = {"org": {"orgnr": "123456789", "navn": "Test AS"}, "risk": {}}
    mock_jq = MagicMock()
    with (
        patch("api.routers.company.fetch_org_profile", return_value=profile),
        patch("api.routers.company.log_audit"),
        patch("api.routers.company.JobQueueService", return_value=mock_jq),
    ):
        client.get("/org/123456789")
    mock_jq.enqueue.assert_called_once()
    assert mock_jq.enqueue.call_args[0][0] == "pdf_extract"


# ── GET /org/{orgnr}/licenses ─────────────────────────────────────────────────


def test_get_org_licenses_returns_200(client):
    # Real fetch_finanstilsynet_licenses returns a list of dicts (see screening_client.py)
    licenses = [
        {
            "name": "Test AS",
            "license_type": "Skadeforsikring",
            "license_status": "Active",
        }
    ]
    with patch(
        "api.routers.company.fetch_finanstilsynet_licenses", return_value=licenses
    ):
        resp = client.get("/org/123456789/licenses")
    assert resp.status_code == 200
    body = resp.json()
    assert body["orgnr"] == "123456789"
    assert len(body["licenses"]) == 1
    assert body["licenses"][0]["license_type"] == "Skadeforsikring"
    assert body["licenses"][0]["license_status"] == "Active"


def test_get_org_licenses_returns_502_on_error(client):
    with patch(
        "api.routers.company.fetch_finanstilsynet_licenses",
        side_effect=_requests.HTTPError("error"),
    ):
        resp = client.get("/org/123456789/licenses")
    assert resp.status_code == 502


# ── GET /companies ────────────────────────────────────────────────────────────


def test_list_companies_returns_list(client):
    companies = [{"orgnr": "123", "navn": "Firma AS", "risk_score": 5}]
    with patch("api.routers.company._list_companies", return_value=companies):
        resp = client.get("/companies")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_list_companies_returns_empty(client):
    with patch("api.routers.company._list_companies", return_value=[]):
        resp = client.get("/companies")
    assert resp.json() == []


def test_list_companies_rejects_invalid_sort_by(client):
    with patch("api.routers.company._list_companies", return_value=[]):
        resp = client.get("/companies?sort_by=invalid_field")
    assert resp.status_code == 422
