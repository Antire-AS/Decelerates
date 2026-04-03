"""Unit tests for api/routers/sla.py — SLA agreement endpoints.

Uses a minimal FastAPI app; SlaService is mocked via dependency override,
and endpoints that query db directly get a MagicMock db session.
"""
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Stub heavy transitive deps before any api.* import
sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.routers.sla import router, _get_sla_service
from api.dependencies import get_db
from api.services.sla_service import SlaService


# ── App fixture ───────────────────────────────────────────────────────────────

_app = FastAPI()
_app.include_router(router)


def _mock_sla(**kwargs):
    row = MagicMock()
    row.id = kwargs.get("id", 1)
    row.created_at = kwargs.get("created_at", "2026-01-15T10:00:00")
    row.client_navn = kwargs.get("client_navn", "Test Firma AS")
    row.client_orgnr = kwargs.get("client_orgnr", "123456789")
    row.client_adresse = kwargs.get("client_adresse", "Testgata 1")
    row.client_kontakt = kwargs.get("client_kontakt", "Ola Nordmann")
    row.start_date = kwargs.get("start_date", "2026-02-01")
    row.account_manager = kwargs.get("account_manager", "Broker Person")
    row.insurance_lines = kwargs.get("insurance_lines", ["Ansvar", "Ulykke"])
    row.fee_structure = kwargs.get("fee_structure", {"type": "provisjon"})
    row.status = kwargs.get("status", "active")
    row.signed_at = kwargs.get("signed_at", None)
    row.signed_by = kwargs.get("signed_by", None)
    row.broker_snapshot = kwargs.get("broker_snapshot", {})
    row.form_data = kwargs.get("form_data", {})
    return row


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_svc():
    return MagicMock(spec=SlaService)


@pytest.fixture
def client(mock_db, mock_svc):
    _app.dependency_overrides[get_db] = lambda: mock_db
    _app.dependency_overrides[_get_sla_service] = lambda: mock_svc
    yield TestClient(_app)
    _app.dependency_overrides.clear()


# ── POST /sla ─────────────────────────────────────────────────────────────────

def test_create_sla_returns_200(client, mock_svc, mock_db):
    agreement = _mock_sla(id=5, created_at="2026-03-01T09:00:00")
    mock_svc.create_agreement.return_value = agreement
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with patch("api.routers.sla.NotificationService"):
        resp = client.post("/sla", json={"form_data": {"client_navn": "Firma AS"}})

    assert resp.status_code == 200


def test_create_sla_returns_id_and_created_at(client, mock_svc, mock_db):
    agreement = _mock_sla(id=7, created_at="2026-03-01T09:00:00")
    mock_svc.create_agreement.return_value = agreement
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with patch("api.routers.sla.NotificationService"):
        resp = client.post("/sla", json={"form_data": {}})

    body = resp.json()
    assert body["id"] == 7
    assert body["created_at"] == "2026-03-01T09:00:00"


def test_create_sla_calls_create_agreement(client, mock_svc, mock_db):
    mock_svc.create_agreement.return_value = _mock_sla()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with patch("api.routers.sla.NotificationService"):
        client.post("/sla", json={"form_data": {"client_navn": "Test"}})

    mock_svc.create_agreement.assert_called_once()


def test_create_sla_swallows_notification_failure(client, mock_svc, mock_db):
    """Notification errors must not cause the endpoint to fail."""
    mock_svc.create_agreement.return_value = _mock_sla()
    broker = MagicMock()
    broker.contact_email = "broker@firm.no"
    mock_db.query.return_value.filter.return_value.first.return_value = broker

    with patch("api.routers.sla.NotificationService") as mock_ns:
        mock_ns.return_value.send_sla_generated.side_effect = Exception("ACS down")
        resp = client.post("/sla", json={"form_data": {}})

    assert resp.status_code == 200


def test_create_sla_returns_422_when_missing_form_data(client, mock_svc, mock_db):
    resp = client.post("/sla", json={})
    assert resp.status_code == 422


# ── GET /sla ──────────────────────────────────────────────────────────────────

def test_list_slas_returns_200(client, mock_db):
    mock_db.query.return_value.order_by.return_value.all.return_value = []
    resp = client.get("/sla")
    assert resp.status_code == 200


def test_list_slas_returns_empty_list_when_no_slas(client, mock_db):
    mock_db.query.return_value.order_by.return_value.all.return_value = []
    resp = client.get("/sla")
    assert resp.json() == []


def test_list_slas_returns_sla_fields(client, mock_db):
    row = _mock_sla(id=3, client_navn="Firma AS", status="active")
    mock_db.query.return_value.order_by.return_value.all.return_value = [row]
    resp = client.get("/sla")
    items = resp.json()
    assert len(items) == 1
    assert items[0]["id"] == 3
    assert items[0]["client_navn"] == "Firma AS"
    assert items[0]["status"] == "active"


def test_list_slas_signed_at_isoformat(client, mock_db):
    from datetime import datetime, timezone
    signed = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    row = _mock_sla(signed_at=signed)
    mock_db.query.return_value.order_by.return_value.all.return_value = [row]
    resp = client.get("/sla")
    item = resp.json()[0]
    assert item["signed_at"] == signed.isoformat()


def test_list_slas_signed_at_none_when_not_signed(client, mock_db):
    row = _mock_sla(signed_at=None)
    mock_db.query.return_value.order_by.return_value.all.return_value = [row]
    resp = client.get("/sla")
    assert resp.json()[0]["signed_at"] is None


# ── PATCH /sla/{sla_id}/sign ──────────────────────────────────────────────────

def test_sign_sla_returns_200(client, mock_svc):
    from datetime import datetime, timezone
    row = _mock_sla(id=1, status="active")
    row.signed_at = datetime(2026, 4, 1, 9, 0, tzinfo=timezone.utc)
    row.signed_by = "Kari Nordmann"
    mock_svc.mark_signed.return_value = row
    resp = client.patch("/sla/1/sign", json={"signed_by": "Kari Nordmann"})
    assert resp.status_code == 200


def test_sign_sla_returns_sla_fields(client, mock_svc):
    from datetime import datetime, timezone
    row = _mock_sla(id=2, status="active")
    row.signed_at = datetime(2026, 4, 2, 9, 0, tzinfo=timezone.utc)
    row.signed_by = "John Doe"
    mock_svc.mark_signed.return_value = row
    resp = client.patch("/sla/2/sign", json={"signed_by": "John Doe"})
    body = resp.json()
    assert body["id"] == 2
    assert body["status"] == "active"
    assert body["signed_by"] == "John Doe"


def test_sign_sla_returns_404_when_not_found(client, mock_svc):
    mock_svc.mark_signed.return_value = None
    resp = client.patch("/sla/999/sign", json={"signed_by": "Anyone"})
    assert resp.status_code == 404


def test_sign_sla_passes_signed_by(client, mock_svc):
    from datetime import datetime, timezone
    row = _mock_sla()
    row.signed_at = datetime.now(timezone.utc)
    row.signed_by = "Person"
    mock_svc.mark_signed.return_value = row
    client.patch("/sla/1/sign", json={"signed_by": "Person"})
    mock_svc.mark_signed.assert_called_once_with(1, signed_by="Person")


def test_sign_sla_strips_whitespace_from_signed_by(client, mock_svc):
    from datetime import datetime, timezone
    row = _mock_sla()
    row.signed_at = datetime.now(timezone.utc)
    row.signed_by = None
    mock_svc.mark_signed.return_value = row
    client.patch("/sla/1/sign", json={"signed_by": "  "})
    # Whitespace-only signed_by becomes None
    mock_svc.mark_signed.assert_called_once_with(1, signed_by=None)


# ── GET /sla/{sla_id} ─────────────────────────────────────────────────────────

def test_get_sla_returns_200(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = _mock_sla(id=4)
    resp = client.get("/sla/4")
    assert resp.status_code == 200


def test_get_sla_returns_sla_dict(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = _mock_sla(
        id=4, client_orgnr="999888777", client_navn="Selskap AS"
    )
    resp = client.get("/sla/4")
    body = resp.json()
    assert body["id"] == 4
    assert body["client_orgnr"] == "999888777"
    assert body["client_navn"] == "Selskap AS"
    assert "insurance_lines" in body
    assert "fee_structure" in body


def test_get_sla_returns_404_when_not_found(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None
    resp = client.get("/sla/999")
    assert resp.status_code == 404


# ── GET /sla/{sla_id}/pdf ─────────────────────────────────────────────────────

def test_download_sla_pdf_returns_200(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = _mock_sla(
        client_orgnr="123456789", created_at="2026-01-15T10:00:00"
    )
    with patch("api.routers.sla._generate_sla_pdf", return_value=b"%PDF-content"):
        resp = client.get("/sla/1/pdf")
    assert resp.status_code == 200


def test_download_sla_pdf_returns_pdf_content_type(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = _mock_sla()
    with patch("api.routers.sla._generate_sla_pdf", return_value=b"%PDF-data"):
        resp = client.get("/sla/1/pdf")
    assert resp.headers["content-type"] == "application/pdf"


def test_download_sla_pdf_returns_404_when_not_found(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None
    resp = client.get("/sla/999/pdf")
    assert resp.status_code == 404


def test_download_sla_pdf_filename_includes_orgnr(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = _mock_sla(
        client_orgnr="111222333", created_at="2026-04-01T08:00:00"
    )
    with patch("api.routers.sla._generate_sla_pdf", return_value=b"%PDF"):
        resp = client.get("/sla/1/pdf")
    cd = resp.headers.get("content-disposition", "")
    assert "111222333" in cd


def test_download_sla_pdf_calls_generate_sla_pdf(client, mock_db):
    row = _mock_sla()
    mock_db.query.return_value.filter.return_value.first.return_value = row
    with patch("api.routers.sla._generate_sla_pdf", return_value=b"%PDF") as mock_gen:
        client.get("/sla/1/pdf")
    mock_gen.assert_called_once_with(row)
