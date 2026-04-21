"""Unit tests for api/routers/contacts.py — contact person endpoints.

Uses a minimal FastAPI app with the router mounted; ContactsService is injected
as a MagicMock — no real DB required.
"""

import sys
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Stub heavy transitive deps before any api.* import
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.auth import CurrentUser, get_current_user
from api.dependencies import get_db
from api.domain.exceptions import NotFoundError
from api.routers.contacts import router, _svc

# ── App fixture ───────────────────────────────────────────────────────────────

_app = FastAPI()
_app.include_router(router)

_FAKE_USER = CurrentUser(
    email="test@local", name="Test User", oid="test-oid", firm_id=1
)


def _mock_contact(**kw):
    c = MagicMock()
    c.id = kw.get("id", 1)
    c.orgnr = kw.get("orgnr", "123456789")
    c.name = kw.get("name", "Ola Nordmann")
    c.title = kw.get("title", "CEO")
    c.email = kw.get("email", "ola@firma.no")
    c.phone = kw.get("phone", "+4712345678")
    c.is_primary = kw.get("is_primary", True)
    c.notes = kw.get("notes", None)
    c.created_at = MagicMock(isoformat=lambda: "2026-04-01T12:00:00")
    return c


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_contacts_svc():
    return MagicMock()


@pytest.fixture
def client(mock_db, mock_contacts_svc):
    _app.dependency_overrides[get_db] = lambda: mock_db
    _app.dependency_overrides[_svc] = lambda: mock_contacts_svc
    _app.dependency_overrides[get_current_user] = lambda: _FAKE_USER
    yield TestClient(_app, raise_server_exceptions=False)
    _app.dependency_overrides.clear()


# ── GET /org/{orgnr}/contacts ────────────────────────────────────────────────


def test_list_contacts_returns_200(client, mock_contacts_svc):
    mock_contacts_svc.list_contacts.return_value = []
    resp = client.get("/org/123456789/contacts")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_contacts_returns_items(client, mock_contacts_svc):
    mock_contacts_svc.list_contacts.return_value = [_mock_contact(id=5, name="Kari")]
    resp = client.get("/org/123456789/contacts")
    items = resp.json()
    assert len(items) == 1
    assert items[0]["id"] == 5
    assert items[0]["name"] == "Kari"


# ── POST /org/{orgnr}/contacts ───────────────────────────────────────────────


def test_create_contact_returns_201(client, mock_contacts_svc):
    mock_contacts_svc.create_contact.return_value = _mock_contact(id=10)
    resp = client.post(
        "/org/123456789/contacts",
        json={"name": "Kari Nordmann"},
    )
    assert resp.status_code == 201
    assert resp.json()["id"] == 10


# ── PUT /org/{orgnr}/contacts/{contact_id} ───────────────────────────────────


def test_update_contact_returns_200(client, mock_contacts_svc):
    mock_contacts_svc.update_contact.return_value = _mock_contact(
        id=3, name="Updated Name"
    )
    resp = client.put(
        "/org/123456789/contacts/3",
        json={"name": "Updated Name"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"


def test_update_contact_returns_404(client, mock_contacts_svc):
    mock_contacts_svc.update_contact.side_effect = NotFoundError("not found")
    resp = client.put(
        "/org/123456789/contacts/999",
        json={"name": "X"},
    )
    assert resp.status_code == 404


# ── DELETE /org/{orgnr}/contacts/{contact_id} ────────────────────────────────


def test_delete_contact_returns_204(client, mock_contacts_svc):
    mock_contacts_svc.delete_contact.return_value = None
    resp = client.delete("/org/123456789/contacts/7")
    assert resp.status_code == 204


def test_delete_contact_returns_404(client, mock_contacts_svc):
    mock_contacts_svc.delete_contact.side_effect = NotFoundError("not found")
    resp = client.delete("/org/123456789/contacts/999")
    assert resp.status_code == 404
