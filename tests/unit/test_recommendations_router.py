"""Unit tests for api/routers/recommendations.py — recommendation letter endpoints.

Uses a minimal FastAPI app with the router mounted; RecommendationService is
injected as a MagicMock — no real DB or Signicat required.
"""
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Stub heavy transitive deps before any api.* import
sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.auth import CurrentUser, get_current_user
from api.dependencies import get_db
from api.domain.exceptions import NotFoundError
from api.routers.recommendations import router, _get_svc

# ── App fixture ───────────────────────────────────────────────────────────────

_app = FastAPI()
_app.include_router(router)

_FAKE_USER = CurrentUser(email="test@local", name="Test User", oid="test-oid", firm_id=1)


def _mock_recommendation(**kw):
    r = MagicMock()
    r.id = kw.get("id", 1)
    r.orgnr = kw.get("orgnr", "123456789")
    r.created_by_email = "test@local"
    r.created_at = MagicMock(isoformat=lambda: "2026-04-01T12:00:00")
    r.idd_id = kw.get("idd_id", 10)
    r.submission_ids = kw.get("submission_ids", [])
    r.recommended_insurer = kw.get("recommended_insurer", "Gjensidige")
    r.rationale_text = kw.get("rationale_text", "Best pris og dekning")
    r.pdf_content = kw.get("pdf_content", None)
    return r


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_svc():
    return MagicMock()


@pytest.fixture
def client(mock_db, mock_svc):
    _app.dependency_overrides[get_db] = lambda: mock_db
    _app.dependency_overrides[_get_svc] = lambda: mock_svc
    _app.dependency_overrides[get_current_user] = lambda: _FAKE_USER
    yield TestClient(_app, raise_server_exceptions=False)
    _app.dependency_overrides.clear()


# ── GET /org/{orgnr}/recommendations ─────────────────────────────────────────

def test_list_recommendations_returns_200(client, mock_svc):
    mock_svc.list.return_value = []
    resp = client.get("/org/123456789/recommendations")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_recommendations_returns_items(client, mock_svc):
    mock_svc.list.return_value = [_mock_recommendation(id=5)]
    resp = client.get("/org/123456789/recommendations")
    items = resp.json()
    assert len(items) == 1
    assert items[0]["id"] == 5
    assert items[0]["recommended_insurer"] == "Gjensidige"


# ── POST /org/{orgnr}/recommendations ────────────────────────────────────────

def test_create_recommendation_returns_201(client, mock_db, mock_svc):
    # IDD check must exist
    idd = MagicMock()
    company = MagicMock()
    company.navn = "Test AS"

    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.first.side_effect = [idd, company]  # IddBehovsanalyse, then Company
    mock_db.query.return_value = mock_query

    mock_svc.create.return_value = _mock_recommendation(id=42)
    resp = client.post(
        "/org/123456789/recommendations",
        json={"recommended_insurer": "If", "submission_ids": [1, 2]},
    )
    assert resp.status_code == 201
    assert resp.json()["id"] == 42


def test_create_recommendation_returns_422_without_idd(client, mock_db, mock_svc):
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.first.return_value = None
    mock_db.query.return_value = mock_query
    resp = client.post(
        "/org/123456789/recommendations",
        json={"recommended_insurer": "If"},
    )
    assert resp.status_code == 422


# ── DELETE /org/{orgnr}/recommendations/{rec_id} ────────────────────────────

def test_delete_recommendation_returns_204(client, mock_svc):
    mock_svc.delete.return_value = None
    resp = client.delete("/org/123456789/recommendations/7")
    assert resp.status_code == 204


def test_delete_recommendation_returns_404(client, mock_svc):
    mock_svc.delete.side_effect = NotFoundError("not found")
    resp = client.delete("/org/123456789/recommendations/999")
    assert resp.status_code == 404


# ── GET /org/{orgnr}/recommendations/{rec_id}/pdf ────────────────────────────

def test_get_recommendation_pdf_cached(client, mock_svc):
    row = _mock_recommendation(pdf_content=b"%PDF-cached")
    mock_svc.get.return_value = row
    resp = client.get("/org/123456789/recommendations/1/pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"


def test_get_recommendation_pdf_not_found(client, mock_svc):
    mock_svc.get.side_effect = NotFoundError("not found")
    resp = client.get("/org/123456789/recommendations/999/pdf")
    assert resp.status_code == 404


# ── POST /org/{orgnr}/recommendations/{rec_id}/sign ──────────────────────────

@patch("api.routers.recommendations.SignicatService")
def test_sign_not_configured_returns_503(mock_signicat_cls, client, mock_svc):
    mock_signicat = MagicMock()
    mock_signicat.is_configured.return_value = False
    mock_signicat_cls.return_value = mock_signicat
    resp = client.post("/org/123456789/recommendations/1/sign")
    assert resp.status_code == 503
