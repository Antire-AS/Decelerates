"""Unit tests for api/routers/financials.py — PDF history, sources, extraction status."""

import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.domain.exceptions import PdfExtractionError
from api.routers.financials import router
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


# ── GET /org/{orgnr}/history ──────────────────────────────────────────────────


def test_get_org_history_returns_200(client):
    with patch("api.routers.financials._get_full_history", return_value=[]):
        resp = client.get("/org/123456789/history")
    assert resp.status_code == 200


def test_get_org_history_returns_years(client):
    years = [{"year": 2023, "sum_driftsinntekter": 1_000_000}]
    with patch("api.routers.financials._get_full_history", return_value=years):
        resp = client.get("/org/123456789/history")
    body = resp.json()
    assert body["orgnr"] == "123456789"
    assert len(body["years"]) == 1
    assert body["years"][0]["year"] == 2023
    # extra='allow' on HistoryRowOut keeps unknown fields
    assert body["years"][0]["sum_driftsinntekter"] == 1_000_000


# ── POST /org/{orgnr}/pdf-history ─────────────────────────────────────────────


def test_add_pdf_history_returns_200(client):
    row = {"year": 2023, "sum_driftsinntekter": 500_000}
    with (
        patch("api.routers.financials.upsert_pdf_source"),
        patch("api.routers.financials.fetch_history_from_pdf", return_value=row),
    ):
        resp = client.post(
            "/org/123456789/pdf-history",
            json={"pdf_url": "https://example.com/r.pdf", "year": 2023},
        )
    assert resp.status_code == 200
    assert resp.json()["orgnr"] == "123456789"


def test_add_pdf_history_returns_502_on_pdf_error(client):
    with (
        patch("api.routers.financials.upsert_pdf_source"),
        patch(
            "api.routers.financials.fetch_history_from_pdf",
            side_effect=PdfExtractionError("parse failed"),
        ),
    ):
        resp = client.post(
            "/org/123456789/pdf-history",
            json={"pdf_url": "https://example.com/r.pdf", "year": 2023},
        )
    assert resp.status_code == 502


def test_add_pdf_history_returns_502_on_generic_error(client):
    with (
        patch("api.routers.financials.upsert_pdf_source"),
        patch(
            "api.routers.financials.fetch_history_from_pdf",
            side_effect=Exception("unexpected"),
        ),
    ):
        resp = client.post(
            "/org/123456789/pdf-history",
            json={"pdf_url": "https://example.com/r.pdf", "year": 2023},
        )
    assert resp.status_code == 502


def test_add_pdf_history_returns_422_when_missing_year(client):
    resp = client.post(
        "/org/123456789/pdf-history", json={"pdf_url": "https://example.com/r.pdf"}
    )
    assert resp.status_code == 422


# ── GET /org/{orgnr}/pdf-sources ──────────────────────────────────────────────


def test_get_pdf_sources_returns_200(client, mock_db):
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    resp = client.get("/org/123456789/pdf-sources")
    assert resp.status_code == 200


def test_get_pdf_sources_returns_source_list(client, mock_db):
    src = MagicMock()
    src.year = 2023
    src.pdf_url = "https://example.com/r.pdf"
    src.label = "Årsrapport 2023"
    src.added_at = "2026-01-01T00:00:00"
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
        src
    ]
    resp = client.get("/org/123456789/pdf-sources")
    sources = resp.json()["sources"]
    assert len(sources) == 1
    assert sources[0]["year"] == 2023


# ── GET /org/{orgnr}/extraction-status ───────────────────────────────────────


def test_extraction_status_no_sources(client, mock_db):
    # No CompanyPdfSource rows → status "no_sources"
    mock_db.query.return_value.filter.return_value.all.return_value = []
    resp = client.get("/org/123456789/extraction-status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "no_sources"


def test_extraction_status_done_when_all_extracted(client, mock_db):
    src = MagicMock()
    src.year = 2020
    history = MagicMock()
    history.year = 2020

    def _query_side_effect(model):
        from api.db import CompanyPdfSource

        q = MagicMock()
        if model is CompanyPdfSource:
            q.filter.return_value.all.return_value = [src]
        else:
            q.filter.return_value.all.return_value = [history]
        return q

    mock_db.query.side_effect = _query_side_effect
    resp = client.get("/org/123456789/extraction-status")
    assert resp.json()["status"] == "done"


# ── DELETE /org/{orgnr}/history ───────────────────────────────────────────────


def test_reset_history_returns_200(client):
    with patch("api.routers.financials.delete_history_year", return_value=5):
        resp = client.delete("/org/123456789/history")
    assert resp.status_code == 200
    assert resp.json()["deleted_rows"] == 5


# ── POST /financials/query ────────────────────────────────────────────────────


def test_nl_query_returns_400_when_empty_question(client):
    resp = client.post("/financials/query", json={"question": "  "})
    assert resp.status_code == 400


def test_nl_query_returns_400_when_missing_question(client):
    resp = client.post("/financials/query", json={})
    assert resp.status_code == 400


def test_nl_query_returns_result(client):
    result = {"sql": "SELECT ...", "columns": ["orgnr"], "rows": [], "error": None}
    with patch("api.services.nl_query.run_nl_query", return_value=result):
        resp = client.post("/financials/query", json={"question": "List all companies"})
    assert resp.status_code == 200


# ── GET /org/{orgnr}/financial-commentary ────────────────────────────────────
# Locks the response shape against FinancialCommentaryOut. The earlier
# implementation returned `{years_analyzed: int, navn: str}` which FastAPI
# silently stripped because neither field is in the schema — see plan §🟡 #6.


def test_financial_commentary_returns_years_list(client, mock_db):
    company = MagicMock()
    company.navn = "Test AS"
    mock_db.query.return_value.filter.return_value.first.return_value = company
    history = [
        {"year": 2022, "sum_driftsinntekter": 1_000_000},
        {"year": 2024, "sum_driftsinntekter": 1_500_000},
        {"year": 2023, "sum_driftsinntekter": 1_200_000},
    ]
    with (
        patch("api.routers.financials._get_full_history", return_value=history),
        patch("api.services.llm._llm_answer_raw", return_value="Lav risiko."),
    ):
        resp = client.get("/org/123456789/financial-commentary")
    assert resp.status_code == 200
    body = resp.json()
    # Schema-enforced shape: only orgnr / commentary / years are present.
    assert set(body.keys()) == {"orgnr", "commentary", "years"}
    assert body["orgnr"] == "123456789"
    assert body["commentary"] == "Lav risiko."
    # Years are returned in chronological order.
    assert body["years"] == [2022, 2023, 2024]


def test_financial_commentary_returns_404_when_no_history(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None
    with patch("api.routers.financials._get_full_history", return_value=[]):
        resp = client.get("/org/123456789/financial-commentary")
    assert resp.status_code == 404
