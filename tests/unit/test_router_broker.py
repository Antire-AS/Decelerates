"""Unit tests for api/routers/broker.py — broker settings + notes endpoints.

Uses a minimal FastAPI app with the router mounted; BrokerService is
injected as a MagicMock — no real DB or network required.
"""
import sys
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Stub heavy transitive deps before any api.* import
sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.auth import CurrentUser, get_current_user
from api.domain.exceptions import NotFoundError
from api.routers.broker import router, _get_broker_service
from api.services.broker import BrokerService


# ── App fixture ───────────────────────────────────────────────────────────────

_app = FastAPI()
_app.include_router(router)


def _mock_settings(**kwargs):
    row = MagicMock()
    row.firm_name = kwargs.get("firm_name", "Test Broker AS")
    row.orgnr = kwargs.get("orgnr", "123456789")
    row.address = kwargs.get("address", "Testgata 1, Oslo")
    row.contact_name = kwargs.get("contact_name", "Ola Nordmann")
    row.contact_email = kwargs.get("contact_email", "ola@broker.no")
    row.contact_phone = kwargs.get("contact_phone", "+4712345678")
    row.updated_at = kwargs.get("updated_at", "2026-01-01T00:00:00")
    return row


def _mock_note(**kwargs):
    note = MagicMock()
    note.id = kwargs.get("id", 1)
    note.text = kwargs.get("text", "Test note")
    note.created_at = kwargs.get("created_at", "2026-01-01T00:00:00")
    return note


@pytest.fixture
def mock_svc():
    return MagicMock(spec=BrokerService)


@pytest.fixture
def client(mock_svc):
    _app.dependency_overrides[_get_broker_service] = lambda: mock_svc
    # Override get_current_user so the F01 dev-user provisioning (which hits
    # the real DB via UserService.get_or_create) is bypassed in this unit
    # test. Without this, CI's test DB — which has no `users` table — fails
    # the POST /broker-notes endpoints.
    _app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        email="test@local", name="Test User", oid="test-oid", firm_id=1,
    )
    yield TestClient(_app)
    _app.dependency_overrides.clear()


# ── GET /broker/settings ──────────────────────────────────────────────────────

def test_get_broker_settings_returns_200(client, mock_svc):
    mock_svc.get_settings.return_value = _mock_settings()
    resp = client.get("/broker/settings")
    assert resp.status_code == 200


def test_get_broker_settings_returns_empty_dict_when_no_settings(client, mock_svc):
    mock_svc.get_settings.return_value = None
    resp = client.get("/broker/settings")
    assert resp.status_code == 200
    assert resp.json() == {}


def test_get_broker_settings_returns_all_fields(client, mock_svc):
    mock_svc.get_settings.return_value = _mock_settings(
        firm_name="Broker Firm", orgnr="987654321"
    )
    resp = client.get("/broker/settings")
    body = resp.json()
    assert body["firm_name"] == "Broker Firm"
    assert body["orgnr"] == "987654321"
    assert "contact_email" in body
    assert "updated_at" in body


def test_get_broker_settings_calls_get_settings(client, mock_svc):
    mock_svc.get_settings.return_value = None
    client.get("/broker/settings")
    mock_svc.get_settings.assert_called_once()


# ── POST /broker/settings ─────────────────────────────────────────────────────

def test_save_broker_settings_returns_200(client, mock_svc):
    mock_svc.save_settings.return_value = _mock_settings()
    resp = client.post("/broker/settings", json={"firm_name": "New Firm"})
    assert resp.status_code == 200


def test_save_broker_settings_calls_save_settings(client, mock_svc):
    mock_svc.save_settings.return_value = _mock_settings()
    client.post("/broker/settings", json={"firm_name": "My Firm", "orgnr": "111222333"})
    mock_svc.save_settings.assert_called_once()


def test_save_broker_settings_returns_422_when_missing_firm_name(client, mock_svc):
    resp = client.post("/broker/settings", json={"orgnr": "123"})
    assert resp.status_code == 422


# ── GET /org/{orgnr}/broker-notes ─────────────────────────────────────────────

def test_list_broker_notes_returns_200(client, mock_svc):
    mock_svc.list_notes.return_value = []
    resp = client.get("/org/123456789/broker-notes")
    assert resp.status_code == 200


def test_list_broker_notes_returns_empty_list_when_no_notes(client, mock_svc):
    mock_svc.list_notes.return_value = []
    resp = client.get("/org/123456789/broker-notes")
    assert resp.json() == []


def test_list_broker_notes_returns_note_fields(client, mock_svc):
    mock_svc.list_notes.return_value = [_mock_note(id=5, text="Important note")]
    resp = client.get("/org/123456789/broker-notes")
    notes = resp.json()
    assert len(notes) == 1
    assert notes[0]["id"] == 5
    assert notes[0]["text"] == "Important note"
    assert "created_at" in notes[0]


def test_list_broker_notes_calls_list_notes_with_orgnr(client, mock_svc):
    mock_svc.list_notes.return_value = []
    client.get("/org/999888777/broker-notes")
    mock_svc.list_notes.assert_called_once_with("999888777")


# ── POST /org/{orgnr}/broker-notes ────────────────────────────────────────────

def test_create_broker_note_returns_200(client, mock_svc):
    mock_svc.create_note.return_value = _mock_note(id=10, created_at="2026-04-01T12:00:00")
    resp = client.post("/org/123456789/broker-notes", json={"text": "New note"})
    assert resp.status_code == 200


def test_create_broker_note_returns_id_and_created_at(client, mock_svc):
    mock_svc.create_note.return_value = _mock_note(id=42, created_at="2026-04-01T12:00:00")
    resp = client.post("/org/123456789/broker-notes", json={"text": "Hello"})
    body = resp.json()
    assert body["id"] == 42
    assert body["created_at"] == "2026-04-01T12:00:00"


def test_create_broker_note_calls_create_note_with_orgnr(client, mock_svc):
    mock_svc.create_note.return_value = _mock_note()
    client.post("/org/555666777/broker-notes", json={"text": "Note text"})
    call_args = mock_svc.create_note.call_args[0]
    assert call_args[0] == "555666777"


def test_create_broker_note_returns_422_when_missing_text(client, mock_svc):
    resp = client.post("/org/123456789/broker-notes", json={})
    assert resp.status_code == 422


# ── DELETE /org/{orgnr}/broker-notes/{note_id} ────────────────────────────────

def test_delete_broker_note_returns_200(client, mock_svc):
    mock_svc.delete_note.return_value = None
    resp = client.delete("/org/123456789/broker-notes/7")
    assert resp.status_code == 200


def test_delete_broker_note_returns_deleted_id(client, mock_svc):
    mock_svc.delete_note.return_value = None
    resp = client.delete("/org/123456789/broker-notes/7")
    assert resp.json() == {"deleted": 7}


def test_delete_broker_note_returns_404_when_not_found(client, mock_svc):
    mock_svc.delete_note.side_effect = NotFoundError("not found")
    resp = client.delete("/org/123456789/broker-notes/999")
    assert resp.status_code == 404


def test_delete_broker_note_calls_delete_note_with_id_and_orgnr(client, mock_svc):
    mock_svc.delete_note.return_value = None
    client.delete("/org/123456789/broker-notes/3")
    mock_svc.delete_note.assert_called_once_with(3, "123456789")
