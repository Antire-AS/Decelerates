"""Integration tests — Knowledge management (ingest, search, chat).

LLM and embedding calls are mocked; DB operations are real.
Requires TEST_DATABASE_URL. Auth is bypassed via dependency override.
Run:
    TEST_DATABASE_URL=postgresql://... uv run python -m pytest tests/integration/test_knowledge.py -v
"""

import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="set TEST_DATABASE_URL=postgresql://... to run integration tests",
)

_FIRM_ID = 40
_ORGNR = "555666777"

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
        "knowledge@firm.no",
        "oid-40",
        _FIRM_ID,
    )
    yield AuthClient(
        TestClient(app), make_user("knowledge@firm.no", "oid-40", _FIRM_ID)
    )
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def seed_data(test_db):
    """Seed a broker firm and a company for knowledge tests."""
    from api.db import BrokerFirm, Company

    if not test_db.query(BrokerFirm).filter(BrokerFirm.id == _FIRM_ID).first():
        test_db.add(
            BrokerFirm(
                id=_FIRM_ID,
                name="Knowledge Test Firma AS",
                created_at=datetime.now(timezone.utc),
            )
        )

    if not test_db.query(Company).filter(Company.orgnr == _ORGNR).first():
        test_db.add(
            Company(
                orgnr=_ORGNR,
                navn="Kunnskapstest AS",
                organisasjonsform_kode="AS",
                naeringskode1="62.010",
                kommune="Oslo",
            )
        )

    test_db.commit()


# ── Ingest knowledge ─────────────────────────────────────────────────────────


class TestIngestKnowledge:
    def test_ingest_returns_chunk_count(self, auth_client):
        with patch("api.routers.knowledge._embed", return_value=None):
            resp = auth_client.post(
                f"/org/{_ORGNR}/ingest-knowledge",
                json={
                    "text": "Selskapet har høy risiko innen cybersikkerhet. "
                    "De mangler grunnleggende sikkerhetstiltak og har "
                    "ikke oppdatert sine systemer på flere år.",
                    "source": "test_note",
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["orgnr"] == _ORGNR
        assert data["source"] == "test_note"
        assert data["chunks_stored"] >= 1

    def test_ingest_empty_text_returns_422(self, auth_client):
        resp = auth_client.post(
            f"/org/{_ORGNR}/ingest-knowledge",
            json={"text": "   ", "source": "empty"},
        )
        assert resp.status_code == 422

    def test_ingest_preserves_chunks_in_db(self, auth_client, test_db):
        """After ingestion, CompanyChunk rows exist for the orgnr."""
        from api.db import CompanyChunk

        with patch("api.routers.knowledge._embed", return_value=None):
            auth_client.post(
                f"/org/{_ORGNR}/ingest-knowledge",
                json={
                    "text": "Viktig informasjon om forsikringsbehov for Kunnskapstest AS.",
                    "source": "persistence_test",
                },
            )

        chunks = (
            test_db.query(CompanyChunk)
            .filter(
                CompanyChunk.orgnr == _ORGNR, CompanyChunk.source == "persistence_test"
            )
            .all()
        )
        assert len(chunks) >= 1
        assert "forsikringsbehov" in chunks[0].chunk_text.lower()


# ── Knowledge search ─────────────────────────────────────────────────────────


class TestKnowledgeSearch:
    def test_search_returns_list(self, auth_client):
        # First ingest something so there's data to find
        with patch("api.routers.knowledge._embed", return_value=None):
            auth_client.post(
                f"/org/{_ORGNR}/ingest-knowledge",
                json={
                    "text": "Eiendomsforsikring dekker skader pa bygninger.",
                    "source": "search_seed",
                },
            )

        with patch("api.routers.knowledge._embed", return_value=None):
            resp = auth_client.get("/knowledge", params={"query": "eiendom"})

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # With embedding mocked to None, fallback is id-desc ordering
        # We just verify the endpoint returns the expected shape
        if data:
            assert "orgnr" in data[0]
            assert "source" in data[0]
            assert "chunk_text" in data[0]

    def test_search_requires_query(self, auth_client):
        resp = auth_client.get("/knowledge")
        assert resp.status_code == 422


# ── Knowledge chat ───────────────────────────────────────────────────────────


class TestKnowledgeChat:
    def test_chat_with_no_indexed_knowledge(self, auth_client):
        """When no knowledge chunks exist, the endpoint returns a helpful message."""
        with patch("api.routers.knowledge._embed", return_value=None):
            resp = auth_client.post(
                "/knowledge/chat",
                json={"question": "Hva sier forskriften?"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "question" in data
        assert "answer" in data
        assert "sources" in data

    def test_chat_with_indexed_knowledge_returns_llm_answer(self, auth_client):
        """After ingesting knowledge, chat returns an LLM-generated answer."""
        # Ingest some knowledge first (into the KNOWLEDGE_ORG namespace)
        from api.services.knowledge_index import KNOWLEDGE_ORG

        with patch("api.routers.knowledge._embed", return_value=None):
            auth_client.post(
                f"/org/{KNOWLEDGE_ORG}/ingest-knowledge",
                json={
                    "text": "Forsikringsavtaleloven regulerer forholdet mellom "
                    "forsikringsselskap og forsikringstaker.",
                    "source": "regulation::FAL",
                },
            )

        with (
            patch("api.routers.knowledge._embed", return_value=None),
            patch(
                "api.routers.knowledge._llm_answer_raw",
                return_value="FAL regulerer forholdet mellom partene i en forsikringsavtale.",
            ),
        ):
            resp = auth_client.post(
                "/knowledge/chat",
                json={"question": "Hva regulerer FAL?"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "FAL" in data["answer"]
        assert isinstance(data["sources"], list)
