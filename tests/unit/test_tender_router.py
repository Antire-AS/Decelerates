"""Unit tests for api/routers/tender_router.py — tender CRUD endpoints."""

import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.auth import CurrentUser, get_current_user
from api.dependencies import get_db
from api.routers.tender_router import router

_app = FastAPI()
_app.include_router(router)

_USER = CurrentUser(email="test@local", name="Test", oid="test-oid", firm_id=1)


@pytest.fixture
def client():
    _app.dependency_overrides[get_current_user] = lambda: _USER
    _app.dependency_overrides[get_db] = lambda: MagicMock()
    yield TestClient(_app)
    _app.dependency_overrides.clear()


@patch("api.routers.tender_router.TenderService")
def test_list_tenders_empty(mock_svc_cls, client):
    mock_svc = MagicMock()
    mock_svc.list_all.return_value = []
    mock_svc_cls.return_value = mock_svc
    resp = client.get("/tenders")
    assert resp.status_code == 200
    assert resp.json() == []


@patch("api.routers.tender_router.TenderService")
def test_get_tender_not_found(mock_svc_cls, client):
    mock_svc = MagicMock()
    mock_svc.get.return_value = None
    mock_svc_cls.return_value = mock_svc
    resp = client.get("/tenders/999")
    assert resp.status_code == 404


@patch("api.routers.tender_router.TenderService")
def test_delete_tender_not_found(mock_svc_cls, client):
    mock_svc = MagicMock()
    mock_svc.delete.return_value = False
    mock_svc_cls.return_value = mock_svc
    resp = client.delete("/tenders/999")
    assert resp.status_code == 404


@patch("api.routers.tender_router.TenderService")
def test_analyse_too_few_offers(mock_svc_cls, client):
    mock_svc = MagicMock()
    mock_svc.analyse_offers.side_effect = ValueError("Minst 2 tilbud")
    mock_svc_cls.return_value = mock_svc
    resp = client.post("/tenders/1/analyse")
    assert resp.status_code == 400
    assert "Minst 2" in resp.json()["detail"]


@patch("api.routers.tender_router.TenderService")
def test_send_tender_not_found(mock_svc_cls, client):
    mock_svc = MagicMock()
    mock_svc.send_invitations.side_effect = ValueError("Tender 1 not found")
    mock_svc_cls.return_value = mock_svc
    resp = client.post("/tenders/1/send")
    assert resp.status_code == 404
