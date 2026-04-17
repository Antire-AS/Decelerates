"""Integration tests — Agent endpoints (recommend-insurers, coverage-gap, copilot chat, risk config).

LLM calls are mocked; everything else (DB, services, rule engine) is real.
Requires TEST_DATABASE_URL. Auth is bypassed via dependency override.
Run:
    TEST_DATABASE_URL=postgresql://... uv run python -m pytest tests/integration/test_agents.py -v
"""

import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="set TEST_DATABASE_URL=postgresql://... to run integration tests",
)

_FIRM_ID = 30
_ORGNR = "777888999"

# ── Shared fixtures ─────────────────────────────────────────────────────────────

from tests.integration.conftest import AuthClient, make_user, resolve_user_factory


@pytest.fixture
def auth_client(test_db):
    from fastapi.testclient import TestClient
    from api.main import app
    from api.auth import get_current_user
    from api.dependencies import get_db

    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_current_user] = resolve_user_factory(
        "agent@firm.no",
        "oid-30",
        _FIRM_ID,
    )
    yield AuthClient(TestClient(app), make_user("agent@firm.no", "oid-30", _FIRM_ID))
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def seed_data(test_db):
    """Seed a broker firm, a company, and an insurer so agent endpoints have data."""
    from api.db import BrokerFirm, Company, Insurer

    if not test_db.query(BrokerFirm).filter(BrokerFirm.id == _FIRM_ID).first():
        test_db.add(
            BrokerFirm(
                id=_FIRM_ID,
                name="Agent Test Firma AS",
                created_at=datetime.now(timezone.utc),
            )
        )

    if not test_db.query(Company).filter(Company.orgnr == _ORGNR).first():
        test_db.add(
            Company(
                orgnr=_ORGNR,
                navn="Testselskap AS",
                organisasjonsform_kode="AS",
                naeringskode1="62.010",
                naeringskode1_beskrivelse="Programvareutvikling",
                kommune="Oslo",
                antall_ansatte=25,
                sum_driftsinntekter=15_000_000,
                sum_eiendeler=8_000_000,
            )
        )

    if (
        not test_db.query(Insurer)
        .filter(
            Insurer.firm_id == _FIRM_ID,
            Insurer.name == "Gjensidige",
        )
        .first()
    ):
        test_db.add(
            Insurer(
                firm_id=_FIRM_ID,
                name="Gjensidige",
                appetite=["Ansvarsforsikring", "Cyberforsikring", "Eiendomsforsikring"],
                created_at=datetime.now(timezone.utc),
            )
        )
        test_db.add(
            Insurer(
                firm_id=_FIRM_ID,
                name="If Skadeforsikring",
                appetite=["Yrkesskadeforsikring", "Transportforsikring"],
                created_at=datetime.now(timezone.utc),
            )
        )

    test_db.commit()


# ── Recommend insurers ───────────────────────────────────────────────────────


class TestRecommendInsurers:
    def test_recommend_returns_recommendations(self, auth_client):
        with patch(
            "api.services.insurer_matching._generate_reasoning",
            return_value="Gjensidige er et godt valg for Testselskap AS.",
        ):
            resp = auth_client.post(
                f"/org/{_ORGNR}/recommend-insurers",
                json={"product_types": ["Ansvarsforsikring"]},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "recommendations" in data
        assert "company" in data
        assert data["company"]["orgnr"] == _ORGNR
        assert len(data["recommendations"]) > 0
        rec = data["recommendations"][0]
        assert "insurer_name" in rec
        assert "score" in rec
        assert "reasoning" in rec

    def test_recommend_empty_when_no_matching_insurers(self, auth_client):
        with patch(
            "api.services.insurer_matching._generate_reasoning",
            return_value="Fallback reasoning.",
        ):
            resp = auth_client.post(
                f"/org/{_ORGNR}/recommend-insurers",
                json={"product_types": ["Sjoforsikring"]},
            )
        assert resp.status_code == 200
        # Still returns a result, even if scores are 0
        data = resp.json()
        assert "recommendations" in data

    def test_recommend_auto_derives_product_types(self, auth_client):
        """When no product_types given, the agent derives them from coverage gaps."""
        with patch(
            "api.services.insurer_matching._generate_reasoning",
            return_value="Auto-derived reasoning.",
        ):
            resp = auth_client.post(f"/org/{_ORGNR}/recommend-insurers")
        assert resp.status_code == 200
        data = resp.json()
        assert "recommendations" in data


# ── Coverage gap ─────────────────────────────────────────────────────────────


class TestCoverageGap:
    def test_coverage_gap_returns_analysis(self, auth_client):
        resp = auth_client.get(f"/org/{_ORGNR}/coverage-gap")
        assert resp.status_code == 200
        data = resp.json()
        assert data["orgnr"] == _ORGNR
        assert "items" in data
        assert isinstance(data["items"], list)
        assert "covered_count" in data
        assert "gap_count" in data
        assert "total_count" in data
        # With no active policies, everything should be a gap
        assert data["covered_count"] == 0
        assert data["gap_count"] == data["total_count"]

    def test_coverage_gap_unknown_company_returns_empty(self, auth_client):
        resp = auth_client.get("/org/000000000/coverage-gap")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total_count"] == 0


# ── Copilot chat (agent + rag modes) ────────────────────────────────────────


class TestCopilotChat:
    def test_chat_rag_mode_returns_answer(self, auth_client):
        with (
            patch("api.routers.knowledge._llm_answer", return_value="Mocked RAG svar."),
            patch("api.routers.knowledge._embed", return_value=None),
            patch(
                "api.routers.knowledge._llm_answer_raw", return_value="Mocked raw svar."
            ),
        ):
            resp = auth_client.post(
                f"/org/{_ORGNR}/chat",
                params={"mode": "rag"},
                json={"question": "Hva er selskapets risikoprofil?"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["orgnr"] == _ORGNR
        assert "answer" in data
        assert "session_id" in data

    def test_chat_agent_mode_returns_answer(self, auth_client):
        mock_result = {
            "answer": "Jeg analyserte dekningsgapet for selskapet.",
            "tool_calls_made": ["coverage_gap"],
        }
        with patch(
            "api.routers.knowledge.chat_with_tools",
            return_value=mock_result,
        ):
            resp = auth_client.post(
                f"/org/{_ORGNR}/chat",
                params={"mode": "agent"},
                json={"question": "Analyser dekningsgapet"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "Jeg analyserte dekningsgapet for selskapet."
        assert "tool_calls" in data

    def test_chat_unknown_company_returns_404(self, auth_client):
        resp = auth_client.post(
            "/org/000000000/chat",
            params={"mode": "rag"},
            json={"question": "Hei"},
        )
        assert resp.status_code == 404


# ── Risk config ──────────────────────────────────────────────────────────────


class TestRiskConfig:
    def test_risk_config_returns_bands(self, auth_client):
        resp = auth_client.get("/risk/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "bands" in data
        assert "max_score" in data
        assert data["max_score"] == 20
        bands = data["bands"]
        assert isinstance(bands, list)
        assert len(bands) > 0
        # Each band should have label, min, max, color
        for band in bands:
            assert "label" in band
            assert "min" in band
            assert "max" in band
            assert "color" in band
