"""Unit tests for api/routers/offers.py — list, download, delete, status update."""

import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.routers.offers import router
from api.dependencies import get_db
from api.limiter import limiter

_app = FastAPI()
_app.state.limiter = limiter
_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
_app.include_router(router)


def _mock_offer(**kwargs):
    offer = MagicMock()
    offer.id = kwargs.get("id", 1)
    offer.filename = kwargs.get("filename", "offer.pdf")
    offer.insurer_name = kwargs.get("insurer_name", "Gjensidige")
    offer.uploaded_at = kwargs.get("uploaded_at", "2026-01-01T10:00:00")
    offer.extracted_text = kwargs.get("extracted_text", "offer text")
    offer.parsed_premie = kwargs.get("parsed_premie", "10 000 kr")
    offer.parsed_dekning = kwargs.get("parsed_dekning", "Ansvar")
    offer.parsed_egenandel = kwargs.get("parsed_egenandel", "5 000 kr")
    offer.parsed_vilkaar = kwargs.get("parsed_vilkaar", None)
    offer.parsed_styrker = kwargs.get("parsed_styrker", None)
    offer.parsed_svakheter = kwargs.get("parsed_svakheter", None)
    offer.pdf_content = kwargs.get("pdf_content", b"%PDF-offer")
    offer.orgnr = kwargs.get("orgnr", "123456789")
    status = MagicMock()
    status.value = kwargs.get("status_value", "pending")
    offer.status = status
    return offer


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def client(mock_db):
    _app.dependency_overrides[get_db] = lambda: mock_db
    yield TestClient(_app)
    _app.dependency_overrides.clear()


# ── GET /org/{orgnr}/offers ───────────────────────────────────────────────────


def test_list_offers_returns_200(client, mock_db):
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    resp = client.get("/org/123456789/offers")
    assert resp.status_code == 200


def test_list_offers_returns_empty_list(client, mock_db):
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    resp = client.get("/org/123456789/offers")
    assert resp.json() == []


def test_list_offers_returns_offer_fields(client, mock_db):
    offer = _mock_offer(id=5, insurer_name="If")
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
        offer
    ]
    resp = client.get("/org/123456789/offers")
    items = resp.json()
    assert len(items) == 1
    assert items[0]["id"] == 5
    assert items[0]["insurer_name"] == "If"
    assert "premie" in items[0]
    assert "status" in items[0]


def test_list_offers_includes_parsed_flag(client, mock_db):
    offer_parsed = _mock_offer(id=1, parsed_premie="5 000 kr")
    offer_unparsed = _mock_offer(id=2, parsed_premie=None)
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
        offer_parsed,
        offer_unparsed,
    ]
    resp = client.get("/org/123456789/offers")
    items = resp.json()
    assert items[0]["parsed"] is True
    assert items[1]["parsed"] is False


# ── GET /org/{orgnr}/offers/{offer_id}/pdf ────────────────────────────────────


def test_download_offer_pdf_returns_200(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = _mock_offer()
    resp = client.get("/org/123456789/offers/1/pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"


def test_download_offer_pdf_returns_pdf_bytes(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = _mock_offer(
        pdf_content=b"%PDF-1.4 offer"
    )
    resp = client.get("/org/123456789/offers/1/pdf")
    assert resp.content == b"%PDF-1.4 offer"


def test_download_offer_pdf_returns_404_when_missing(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None
    resp = client.get("/org/123456789/offers/999/pdf")
    assert resp.status_code == 404


def test_download_offer_pdf_filename_in_header(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = _mock_offer(
        filename="gjensidige_2023.pdf"
    )
    resp = client.get("/org/123456789/offers/1/pdf")
    assert "gjensidige_2023.pdf" in resp.headers.get("content-disposition", "")


# ── DELETE /org/{orgnr}/offers/{offer_id} ─────────────────────────────────────


def test_delete_offer_returns_200(client, mock_db):
    with (
        patch("api.routers.offers.remove_insurance_offer", return_value=True),
        patch("api.routers.offers.log_audit"),
    ):
        resp = client.delete("/org/123456789/offers/1")
    assert resp.status_code == 200
    assert resp.json() == {"deleted": 1}


def test_delete_offer_returns_404_when_missing(client, mock_db):
    with patch("api.routers.offers.remove_insurance_offer", return_value=False):
        resp = client.delete("/org/123456789/offers/999")
    assert resp.status_code == 404


# ── PATCH /org/{orgnr}/offers/{offer_id}/status ───────────────────────────────


def test_set_offer_status_returns_200(client, mock_db):
    with (
        patch("api.routers.offers.update_offer_status", return_value=True),
        patch("api.routers.offers.log_audit"),
    ):
        resp = client.patch(
            "/org/123456789/offers/1/status", json={"status": "accepted"}
        )
    assert resp.status_code == 200
    assert resp.json() == {"id": 1, "status": "accepted"}


def test_set_offer_status_returns_400_when_status_missing(client, mock_db):
    resp = client.patch("/org/123456789/offers/1/status", json={})
    assert resp.status_code == 400


def test_set_offer_status_returns_404_when_offer_missing(client, mock_db):
    with patch("api.routers.offers.update_offer_status", return_value=False):
        resp = client.patch(
            "/org/123456789/offers/999/status", json={"status": "rejected"}
        )
    assert resp.status_code == 404


def test_set_offer_status_returns_400_when_whitespace_only(client, mock_db):
    resp = client.patch("/org/123456789/offers/1/status", json={"status": "   "})
    assert resp.status_code == 400
