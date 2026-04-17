"""Unit tests for api/routers/risk_router.py — risk offer, coverage gap, narrative, PDF endpoints.

Uses a minimal FastAPI app with the router mounted; LLM calls, DB queries, and
PDF generation are all mocked — no real infrastructure required.
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
from api.routers.risk_router import router, _get_notification

# ── App fixture ───────────────────────────────────────────────────────────────

_app = FastAPI()
_app.include_router(router)

_FAKE_USER = CurrentUser(
    email="test@local", name="Test User", oid="test-oid", firm_id=1
)


def _mock_company(**kw):
    c = MagicMock()
    c.orgnr = kw.get("orgnr", "123456789")
    c.navn = kw.get("navn", "Test AS")
    c.organisasjonsform_kode = "AS"
    c.kommune = "Oslo"
    c.naeringskode1 = "62.010"
    c.naeringskode1_beskrivelse = "Programmeringstjenester"
    c.sum_driftsinntekter = 10_000_000
    c.sum_egenkapital = 3_000_000
    c.sum_eiendeler = 8_000_000
    c.regnskap_raw = {}
    c.pep_raw = {}
    c.risk_score = 5
    return c


@pytest.fixture
def mock_db():
    db = MagicMock()
    return db


@pytest.fixture
def mock_notification():
    return MagicMock()


@pytest.fixture
def client(mock_db, mock_notification):
    _app.dependency_overrides[get_db] = lambda: mock_db
    _app.dependency_overrides[get_current_user] = lambda: _FAKE_USER
    _app.dependency_overrides[_get_notification] = lambda: mock_notification
    yield TestClient(_app, raise_server_exceptions=False)
    _app.dependency_overrides.clear()


# ── GET /risk/config ─────────────────────────────────────────────────────────


def test_risk_config_returns_200(client):
    resp = client.get("/risk/config")
    assert resp.status_code == 200
    body = resp.json()
    assert "bands" in body
    assert body["max_score"] == 20


# ── POST /org/{orgnr}/risk-offer ─────────────────────────────────────────────


@patch("api.routers.risk_router._save_to_rag")
@patch("api.routers.risk_router._parse_json_from_llm_response")
@patch("api.routers.risk_router._llm_answer_raw")
@patch("api.routers.risk_router.fetch_ssb_benchmark", return_value={})
@patch("api.routers.risk_router.derive_simple_risk")
def test_risk_offer_returns_200(
    mock_risk, mock_bench, mock_llm, mock_parse, mock_rag, client, mock_db
):
    mock_risk.return_value = {"score": 5, "factors": []}
    mock_llm.return_value = "some LLM text"
    mock_parse.return_value = {
        "sammendrag": "Test",
        "anbefalinger": [],
        "total_premieanslag": "100k",
    }
    company = _mock_company()
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = company
    mock_db.query.return_value = mock_query
    resp = client.post("/org/123456789/risk-offer")
    assert resp.status_code == 200
    assert resp.json()["orgnr"] == "123456789"


def test_risk_offer_returns_404_when_no_company(client, mock_db):
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None
    mock_db.query.return_value = mock_query
    resp = client.post("/org/999999999/risk-offer")
    assert resp.status_code == 404


# ── POST /org/{orgnr}/coverage-gap ───────────────────────────────────────────


@patch("api.routers.risk_router._save_gap_to_rag")
@patch("api.routers.risk_router._parse_json_from_llm_response")
@patch("api.routers.risk_router._llm_answer_raw")
@patch("api.routers.risk_router.derive_simple_risk")
def test_coverage_gap_returns_200(
    mock_risk, mock_llm, mock_parse, mock_rag, client, mock_db
):
    mock_risk.return_value = {"score": 3, "factors": []}
    mock_llm.return_value = "gap analysis"
    mock_parse.return_value = {
        "dekket": ["brann"],
        "mangler": ["cyber"],
        "anbefaling": "Kjøp cyber",
    }

    company = _mock_company()
    offer = MagicMock()
    offer.insurer_name = "Gjensidige"
    offer.filename = "tilbud.pdf"
    offer.extracted_text = "policy text"

    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = company
    mock_query.all.return_value = [offer]
    mock_db.query.return_value = mock_query

    resp = client.post("/org/123456789/coverage-gap")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_coverage_gap_no_offers(client, mock_db):
    company = _mock_company()
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = company
    mock_query.all.return_value = []
    mock_db.query.return_value = mock_query
    resp = client.post("/org/123456789/coverage-gap")
    assert resp.status_code == 200
    assert resp.json()["status"] == "no_offers"


# ── GET /org/{orgnr}/risk-report/pdf ─────────────────────────────────────────


@patch("api.routers.risk_router.generate_risk_report_pdf", return_value=b"%PDF-fake")
@patch("api.routers.risk_router.derive_simple_risk")
def test_risk_report_pdf_returns_pdf(mock_risk, mock_gen, client, mock_db):
    mock_risk.return_value = {"score": 7, "factors": []}
    company = _mock_company()
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = company
    mock_db.query.return_value = mock_query
    resp = client.get("/org/123456789/risk-report/pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"


def test_risk_report_pdf_returns_404(client, mock_db):
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None
    mock_db.query.return_value = mock_query
    resp = client.get("/org/999999999/risk-report/pdf")
    assert resp.status_code == 404


# ── POST /org/{orgnr}/narrative ──────────────────────────────────────────────


@patch("api.routers.risk_router._save_to_rag")
@patch(
    "api.routers.risk_router._generate_risk_narrative",
    return_value="Risk analysis text",
)
@patch("api.routers.risk_router.fetch_board_members", return_value=[])
@patch("api.routers.risk_router.derive_simple_risk")
def test_narrative_returns_200(
    mock_risk, mock_members, mock_gen, mock_rag, client, mock_db
):
    mock_risk.return_value = {"score": 4, "factors": []}
    company = _mock_company()
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = company
    mock_db.query.return_value = mock_query
    resp = client.post("/org/123456789/narrative")
    assert resp.status_code == 200
    assert resp.json()["narrative"] == "Risk analysis text"


# ── POST /org/{orgnr}/forsikringstilbud/pdf ──────────────────────────────────


@patch("api.routers.risk_router.save_insurance_document")
@patch(
    "api.routers.risk_router._build_forsikringstilbud_pdf", return_value=b"%PDF-tilbud"
)
@patch(
    "api.routers.risk_router._broker_info_from_db",
    return_value=("Broker AS", "Ola", "ola@b.no", "+47123"),
)
@patch("api.routers.risk_router._extract_offer_summary", return_value={"selskap": "X"})
def test_forsikringstilbud_pdf_returns_pdf(
    mock_sum, mock_broker, mock_build, mock_save, client, mock_db
):
    company = _mock_company()
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = company
    mock_query.all.return_value = []
    mock_db.query.return_value = mock_query
    resp = client.post(
        "/org/123456789/forsikringstilbud/pdf",
        json={"anbefalinger": [], "total_premieanslag": "50k", "sammendrag": "Test"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"


# ── POST /org/{orgnr}/forsikringstilbud/email ─────────────────────────────────


@patch("api.routers.risk_router.log_audit")
@patch("api.routers.risk_router.get_or_create_active_token")
def test_forsikringstilbud_email_returns_200(
    mock_token, mock_audit, client, mock_db, mock_notification
):
    token_row = MagicMock()
    token_row.token = "abc-token-123"
    mock_token.return_value = token_row
    mock_notification.send_forsikringstilbud.return_value = True

    company = _mock_company()
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = company
    mock_db.query.return_value = mock_query

    resp = client.post(
        "/org/123456789/forsikringstilbud/email",
        json={"recipient_email": "kontakt@firma.no"},
    )
    assert resp.status_code == 200
    assert resp.json()["sent"] is True
