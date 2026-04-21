"""Unit tests for api/routers/company.py — additional coverage for insurance-needs
and peer-benchmark endpoints plus org-by-name.

Complements test_router_company.py which covers ping, search, org profile, licenses,
and companies list.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.routers.company import router
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


# ── GET /org/{orgnr}/insurance-needs ─────────────────────────────────────────


def test_insurance_needs_from_db_company(client, mock_db):
    db_obj = MagicMock(
        orgnr="123456789",
        navn="Test AS",
        naeringskode1="64.11",
        organisasjonsform_kode="AS",
        antall_ansatte=50,
        sum_driftsinntekter=5_000_000,
        sum_eiendeler=2_000_000,
        sum_egenkapital=1_000_000,
    )
    # First query().filter().first() returns the Company
    mock_db.query.return_value.filter.return_value.first.return_value = db_obj
    # Second query (CompanyHistory) chain
    mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

    needs = [{"product": "Ansvar", "priority": "high"}]
    with (
        patch("api.routers.company.estimate_insurance_needs", return_value=needs),
        patch(
            "api.routers.company.build_insurance_narrative",
            return_value="narrative text",
        ),
    ):
        resp = client.get("/org/123456789/insurance-needs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["orgnr"] == "123456789"
    assert body["needs"] == needs
    assert body["narrative"] == "narrative text"


def test_insurance_needs_fetches_from_brreg_when_not_in_db(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None
    brreg = {
        "navn": "New AS",
        "naeringskode1": {"kode": "46.90"},
        "organisasjonsform": {"kode": "AS"},
        "antallAnsatte": 10,
    }

    with (
        patch("api.services.fetch_enhet_by_orgnr", return_value=brreg),
        patch("api.routers.company.estimate_insurance_needs", return_value=[]),
        patch("api.routers.company.build_insurance_narrative", return_value=""),
    ):
        resp = client.get("/org/999999999/insurance-needs")
    assert resp.status_code == 200


def test_insurance_needs_returns_404_when_brreg_empty(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None
    with patch("api.services.fetch_enhet_by_orgnr", return_value={}):
        resp = client.get("/org/000000000/insurance-needs")
    assert resp.status_code == 404


# ── GET /org/{orgnr}/peer-benchmark ──────────────────────────────────────────


def test_peer_benchmark_returns_db_peers(client, mock_db):
    company = MagicMock(
        orgnr="123456789",
        naeringskode1="64.11",
        equity_ratio=0.35,
        sum_driftsinntekter=5_000_000,
        risk_score=3,
    )
    peer1 = MagicMock(
        equity_ratio=0.40,
        sum_driftsinntekter=6_000_000,
        risk_score=2,
    )
    peer2 = MagicMock(
        equity_ratio=0.30,
        sum_driftsinntekter=4_000_000,
        risk_score=4,
    )
    peer3 = MagicMock(
        equity_ratio=0.25,
        sum_driftsinntekter=3_000_000,
        risk_score=5,
    )

    def _query_side_effect(model):
        q = MagicMock()
        # Company lookup
        q.filter.return_value.first.return_value = company
        # Peer query
        q.filter.return_value.filter.return_value.all.return_value = [
            peer1,
            peer2,
            peer3,
        ]
        return q

    mock_db.query.side_effect = _query_side_effect

    resp = client.get("/org/123456789/peer-benchmark")
    assert resp.status_code == 200
    body = resp.json()
    assert body["orgnr"] == "123456789"
    assert "metrics" in body


def test_peer_benchmark_returns_404_for_unknown_company(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None
    resp = client.get("/org/000000000/peer-benchmark")
    assert resp.status_code == 404


# ── GET /org-by-name ─────────────────────────────────────────────────────────


def test_org_by_name_returns_404_when_no_match(client):
    with patch("api.routers.company.fetch_enhetsregisteret", return_value=[]):
        resp = client.get("/org-by-name?name=NonexistentCorp")
    assert resp.status_code == 404


def test_org_by_name_rejects_single_char(client):
    resp = client.get("/org-by-name?name=X")
    assert resp.status_code == 422
