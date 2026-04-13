"""Unit tests for api/routers/portfolio_router.py — portfolio CRUD + agents."""
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.auth import CurrentUser, get_current_user
from api.domain.exceptions import NotFoundError
from api.routers.portfolio_router import router, _svc
from api.services.portfolio import PortfolioService

_app = FastAPI()
_app.include_router(router)

_USER = CurrentUser(email="test@local", name="Test", oid="test-oid", firm_id=1)


def _portfolio_mock(id=1, name="Test Portfolio"):
    p = MagicMock()
    p.id = id
    p.name = name
    p.description = "Test"
    p.firm_id = 1
    p.created_at = MagicMock(isoformat=lambda: "2026-01-01T00:00:00")
    return p


@pytest.fixture
def mock_svc():
    return MagicMock(spec=PortfolioService)


@pytest.fixture
def client(mock_svc):
    _app.dependency_overrides[_svc] = lambda: mock_svc
    _app.dependency_overrides[get_current_user] = lambda: _USER
    yield TestClient(_app)
    _app.dependency_overrides.clear()


# ── GET /portfolio ────────────────────────────────────────────────────────────

def test_list_portfolios(client, mock_svc):
    mock_svc.list_portfolios.return_value = [_portfolio_mock()]
    resp = client.get("/portfolio")
    assert resp.status_code == 200


# ── POST /portfolio ───────────────────────────────────────────────────────────

def test_create_portfolio(client, mock_svc):
    mock_svc.create.return_value = _portfolio_mock()
    resp = client.post("/portfolio", json={"name": "New", "description": "Desc"})
    assert resp.status_code == 200


# ── GET /portfolio/{id} ──────────────────────────────────────────────────────

def test_get_portfolio(client, mock_svc):
    mock_svc.get.return_value = _portfolio_mock()
    resp = client.get("/portfolio/1")
    assert resp.status_code == 200


def test_get_portfolio_not_found(client, mock_svc):
    mock_svc.get.side_effect = NotFoundError("nope")
    resp = client.get("/portfolio/999")
    assert resp.status_code == 404


# ── DELETE /portfolio/{id} ────────────────────────────────────────────────────

def test_delete_portfolio(client, mock_svc):
    mock_svc.delete.return_value = None
    resp = client.delete("/portfolio/1")
    assert resp.status_code == 200


# ── POST /portfolio/{id}/companies ────────────────────────────────────────────

def test_add_company(client, mock_svc):
    mock_svc.add_company.return_value = None
    resp = client.post("/portfolio/1/companies", json={"orgnr": "123456789"})
    assert resp.status_code == 200
    assert resp.json()["orgnr"] == "123456789"


def test_add_company_not_found(client, mock_svc):
    mock_svc.add_company.side_effect = NotFoundError("nope")
    resp = client.post("/portfolio/1/companies", json={"orgnr": "000"})
    assert resp.status_code == 404


# ── POST /portfolio/{id}/companies/bulk ───────────────────────────────────────

def test_bulk_add_companies(client, mock_svc):
    mock_svc.get.return_value = _portfolio_mock()
    mock_svc.add_company.return_value = None
    resp = client.post("/portfolio/1/companies/bulk", json={"orgnrs": ["123", "456"]})
    assert resp.status_code == 200
    assert resp.json()["added"] == 2


# ── DELETE /portfolio/{id}/companies/{orgnr} ──────────────────────────────────

def test_remove_company(client, mock_svc):
    mock_svc.remove_company.return_value = None
    resp = client.delete("/portfolio/1/companies/123456789")
    assert resp.status_code == 200


