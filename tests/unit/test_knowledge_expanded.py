"""Expanded unit tests for api/routers/knowledge.py — chat endpoints, seed-regulations, agent mode.

Covers POST /org/{orgnr}/chat (RAG + agent modes), POST /knowledge/seed-regulations,
helper functions _readable_source, _chunk_snippet, and _auto_ingest_company_data.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Specific rag_chain behaviour is patched per-test via `@patch(...)`.
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.auth import CurrentUser, get_current_user
from api.domain.exceptions import LlmUnavailableError, QuotaError
from api.routers.knowledge import router, _readable_source, _chunk_snippet
from api.dependencies import get_db
from api.limiter import limiter

_app = FastAPI()
_app.state.limiter = limiter
_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
_app.include_router(router)

_FAKE_USER = CurrentUser(email="test@local", name="Test", oid="test-oid", firm_id=1)


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def client(mock_db):
    _app.dependency_overrides[get_db] = lambda: mock_db
    _app.dependency_overrides[get_current_user] = lambda: _FAKE_USER
    yield TestClient(_app, raise_server_exceptions=False)
    _app.dependency_overrides.clear()


def _mock_company(orgnr="123456789", navn="Test AS"):
    c = MagicMock()
    c.orgnr = orgnr
    c.navn = navn
    return c

    # ── POST /org/{orgnr}/chat (RAG mode) ───────────────────────────────────────

    with (
        patch("api.routers.knowledge._auto_ingest_company_data"),
        patch("api.routers.knowledge._build_history_context", return_value=""),
        patch(
            "api.routers.knowledge._answer_with_rag_or_notes", return_value="AI answer"
        ),
        patch("api.routers.knowledge.save_qa_note", return_value=1),
        patch("api.routers.knowledge._chunk_and_store"),
    ):
        resp = client.post("/org/123456789/chat", json={"question": "Hva er risikoen?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "AI answer"
    assert body["orgnr"] == "123456789"

    with (
        patch("api.routers.knowledge._auto_ingest_company_data"),
        patch("api.routers.knowledge._build_history_context", return_value=""),
        patch(
            "api.routers.knowledge._answer_with_rag_or_notes",
            side_effect=QuotaError("quota"),
        ),
    ):
        resp = client.post("/org/123456789/chat", json={"question": "?"})
    assert resp.status_code == 429

    with (
        patch("api.routers.knowledge._auto_ingest_company_data"),
        patch("api.routers.knowledge._build_history_context", return_value=""),
        patch(
            "api.routers.knowledge._answer_with_rag_or_notes",
            side_effect=LlmUnavailableError("no key"),
        ),
    ):
        resp = client.post("/org/123456789/chat", json={"question": "?"})
    assert resp.status_code == 503

    # ── POST /org/{orgnr}/chat (agent mode) ─────────────────────────────────────

    agent_result = {"answer": "Agent says hello", "tool_calls_made": ["search"]}
    with (
        patch("api.routers.knowledge.chat_with_tools", return_value=agent_result),
        patch("api.routers.knowledge.save_qa_note", return_value=1),
    ):
        resp = client.post(
            "/org/123456789/chat?mode=agent", json={"question": "Finn info"}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "Agent says hello"
    assert "tool_calls" in body

    # ── POST /knowledge/seed-regulations ─────────────────────────────────────────

    with (
        patch(
            "api.routers.knowledge._fetch_regulation_text",
            return_value="Lov om forsikring " * 50,
        ),
        patch("api.routers.knowledge._chunk_and_store", return_value=10),
    ):
        resp = client.post("/knowledge/seed-regulations")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_chunks"] > 0
    assert len(body["seeded"]) == 3

    resp = client.post("/knowledge/seed-regulations")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_chunks"] == 0
    assert all(s["status"] == "already_indexed" for s in body["seeded"])


# ── _readable_source helper ──────────────────────────────────────────────────


def test_readable_source_video():
    result = _readable_source("video::MyVideo::120::Kapittel 2")
    assert "MyVideo" in result
    assert "2:00" in result


def test_readable_source_doc():
    result = _readable_source("doc::category::Forsikringspolise")
    assert result == "Forsikringspolise"


def test_readable_source_plain():
    assert _readable_source("annual_report_2023") == "annual_report_2023"


# ── _chunk_snippet helper ────────────────────────────────────────────────────


def test_chunk_snippet_truncates():
    long_text = "Relevant insurance text. " * 20
    result = _chunk_snippet(long_text, max_len=50)
    assert len(result) <= 55  # 50 + ellipsis


def test_chunk_snippet_skips_headers():
    text = "Video: Some video\nKapittel: Ch1\nActual content here."
    result = _chunk_snippet(text)
    assert "Actual content" in result
    assert "Video:" not in result
