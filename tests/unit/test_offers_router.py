"""Unit tests for api/routers/offers.py — insurance offer endpoints.

Uses a minimal FastAPI app with the router mounted; DB queries, LLM calls,
and PDF parsing are all mocked — no real infrastructure required.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Stub heavy transitive deps before any api.* import
sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.dependencies import get_db
from api.routers.offers import router

# ── App fixture ───────────────────────────────────────────────────────────────

_app = FastAPI()
_app.include_router(router)


def _mock_offer(**kw):
    o = MagicMock()
    o.id = kw.get("id", 1)
    o.filename = kw.get("filename", "tilbud.pdf")
    o.insurer_name = kw.get("insurer_name", "Gjensidige")
    o.uploaded_at = "2026-04-01T12:00:00"
    o.extracted_text = kw.get("extracted_text", "policy text")
    o.parsed_premie = kw.get("parsed_premie", None)
    o.parsed_dekning = None
    o.parsed_egenandel = None
    o.parsed_vilkaar = None
    o.parsed_styrker = None
    o.parsed_svakheter = None
    o.pdf_content = kw.get("pdf_content", b"%PDF-fake")
    o.orgnr = kw.get("orgnr", "123456789")
    o.status = MagicMock(value="pending")
    return o


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def client(mock_db):
    _app.dependency_overrides[get_db] = lambda: mock_db
    yield TestClient(_app, raise_server_exceptions=False)
    _app.dependency_overrides.clear()


# ── GET /org/{orgnr}/offers ──────────────────────────────────────────────────


def test_list_offers_returns_200(client, mock_db):
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.all.return_value = []
    mock_db.query.return_value = mock_query
    resp = client.get("/org/123456789/offers")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_offers_returns_items(client, mock_db):
    offer = _mock_offer(id=5, insurer_name="If")
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.all.return_value = [offer]
    mock_db.query.return_value = mock_query
    resp = client.get("/org/123456789/offers")
    items = resp.json()
    assert len(items) == 1
    assert items[0]["id"] == 5
    assert items[0]["insurer_name"] == "If"


# ── DELETE /org/{orgnr}/offers/{offer_id} ────────────────────────────────────


@patch("api.routers.offers.log_audit")
@patch("api.routers.offers.remove_insurance_offer", return_value=True)
def test_delete_offer_returns_200(mock_remove, mock_audit, client):
    resp = client.delete("/org/123456789/offers/7")
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 7


@patch("api.routers.offers.log_audit")
@patch("api.routers.offers.remove_insurance_offer", return_value=False)
def test_delete_offer_returns_404(mock_remove, mock_audit, client):
    resp = client.delete("/org/123456789/offers/999")
    assert resp.status_code == 404


# ── GET /org/{orgnr}/offers/{offer_id}/pdf ───────────────────────────────────


def test_download_offer_pdf_returns_pdf(client, mock_db):
    offer = _mock_offer(pdf_content=b"%PDF-real")
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = offer
    mock_db.query.return_value = mock_query
    resp = client.get("/org/123456789/offers/1/pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"


def test_download_offer_pdf_returns_404(client, mock_db):
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None
    mock_db.query.return_value = mock_query
    resp = client.get("/org/123456789/offers/999/pdf")
    assert resp.status_code == 404


# ── PATCH /org/{orgnr}/offers/{offer_id}/status ─────────────────────────────


@patch("api.routers.offers.log_audit")
@patch("api.routers.offers.update_offer_status", return_value=True)
def test_update_offer_status_returns_200(mock_update, mock_audit, client):
    resp = client.patch("/org/123456789/offers/1/status", json={"status": "accepted"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"


@patch("api.routers.offers.log_audit")
@patch("api.routers.offers.update_offer_status", return_value=False)
def test_update_offer_status_returns_404(mock_update, mock_audit, client):
    resp = client.patch("/org/123456789/offers/1/status", json={"status": "rejected"})
    assert resp.status_code == 404


def test_update_offer_status_missing_status(client):
    resp = client.patch("/org/123456789/offers/1/status", json={})
    assert resp.status_code == 400


# ── POST /org/{orgnr}/offers/compare-stored ──────────────────────────────────


@patch("api.routers.offers._compare_offers_with_llm", return_value="comparison text")
def test_compare_stored_offers_returns_200(mock_compare, client, mock_db):
    offer1 = _mock_offer(id=1, insurer_name="If")
    offer2 = _mock_offer(id=2, insurer_name="Gjensidige")
    company = MagicMock()
    company.navn = "Test AS"
    company.naeringskode1_beskrivelse = "IT"
    company.risk_score = 5

    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = [offer1, offer2]
    mock_query.first.return_value = company
    mock_db.query.return_value = mock_query

    resp = client.post("/org/123456789/offers/compare-stored", json=[1, 2])
    assert resp.status_code == 200
    assert resp.json()["comparison"] == "comparison text"
