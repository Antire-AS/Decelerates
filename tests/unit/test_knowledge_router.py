"""Unit tests for api/routers/knowledge.py — org chat + knowledge chat endpoints.

Uses a minimal FastAPI app with the router mounted; all LLM and DB calls are
mocked — no real database, AI providers, or network required.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Stub heavy transitive deps before any api.* import
sys.modules.setdefault("api.services.pdf_background", MagicMock())
sys.modules.setdefault("api.services.copilot_agent", MagicMock())
sys.modules.setdefault("api.services.knowledge_index", MagicMock())

from api.auth import CurrentUser, get_current_user
from api.dependencies import get_db
from api.routers.knowledge import router

# -- App fixture ---------------------------------------------------------------

_app = FastAPI()
_app.include_router(router)


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.all.return_value = []
    db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
    return db


@pytest.fixture
def client(mock_db):
    _app.dependency_overrides[get_db] = lambda: mock_db
    _app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        email="test@local",
        name="Test User",
        oid="test-oid",
        firm_id=1,
    )
    yield TestClient(_app)
    _app.dependency_overrides.clear()


# -- POST /org/{orgnr}/chat (mode=rag) ----------------------------------------


@patch("api.routers.knowledge._chunk_and_store", return_value=1)
@patch("api.routers.knowledge.save_qa_note", return_value=42)
@patch("api.routers.knowledge._answer_with_rag_or_notes", return_value="Test answer")
@patch("api.routers.knowledge._auto_ingest_company_data")
def test_org_chat_rag_mode(
    mock_ingest, mock_answer, mock_save, mock_chunk, client, mock_db
):
    db_obj = MagicMock()
    db_obj.orgnr = "123456789"
    mock_db.query.return_value.filter.return_value.first.return_value = db_obj
    resp = client.post(
        "/org/123456789/chat?mode=rag", json={"question": "What is revenue?"}
    )
    assert resp.status_code == 200
    assert resp.json()["answer"] == "Test answer"


@patch("api.routers.knowledge._chunk_and_store", return_value=1)
@patch("api.routers.knowledge.save_qa_note", return_value=42)
@patch("api.routers.knowledge._answer_with_rag_or_notes", return_value="reply")
@patch("api.routers.knowledge._auto_ingest_company_data")
def test_org_chat_returns_session_id(mock_i, mock_a, mock_s, mock_c, client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock()
    resp = client.post("/org/123/chat?mode=rag", json={"question": "hi"})
    assert "session_id" in resp.json()
    assert resp.json()["session_id"]  # non-empty


def test_org_chat_404_when_company_missing(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None
    resp = client.post("/org/000000000/chat?mode=rag", json={"question": "test"})
    assert resp.status_code == 404


# -- POST /org/{orgnr}/chat (mode=agent) --------------------------------------


@patch("api.routers.knowledge.save_qa_note", return_value=1)
@patch("api.routers.knowledge._chat_agent_mode")
def test_org_chat_agent_mode(mock_agent, mock_save, client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock()
    mock_agent.return_value = {
        "orgnr": "123",
        "question": "hi",
        "answer": "agent reply",
        "session_id": "s1",
        "tool_calls": [],
    }
    resp = client.post("/org/123/chat?mode=agent", json={"question": "hi"})
    assert resp.status_code == 200
    assert resp.json()["answer"] == "agent reply"


# -- DELETE /org/{orgnr}/chat --------------------------------------------------


@patch("api.routers.knowledge._clear_chat_session", return_value=3)
def test_delete_chat_session(mock_clear, client, mock_db):
    resp = client.delete("/org/123/chat?session_id=s1")
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 3
    mock_clear.assert_called_once_with("123", "s1", mock_db)


# -- GET /org/{orgnr}/chat (history) ------------------------------------------


def test_get_chat_history_empty(client, mock_db):
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    resp = client.get("/org/123/chat")
    assert resp.status_code == 200
    assert resp.json() == []


# -- POST /knowledge/chat -----------------------------------------------------


@patch("api.routers.knowledge._llm_answer_raw", return_value="knowledge reply")
@patch("api.routers.knowledge._retrieve_knowledge_chunks")
def test_knowledge_chat_with_chunks(mock_retrieve, mock_llm, client):
    mock_retrieve.return_value = [{"text": "chunk text", "source": "video::a::0::ch"}]
    resp = client.post("/knowledge/chat", json={"question": "what is IDD?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "knowledge reply"
    assert len(body["sources"]) == 1


@patch("api.routers.knowledge._retrieve_knowledge_chunks", return_value=[])
def test_knowledge_chat_no_chunks_returns_fallback(mock_retrieve, client):
    resp = client.post("/knowledge/chat", json={"question": "anything"})
    assert resp.status_code == 200
    assert "indeksert" in resp.json()["answer"].lower()
