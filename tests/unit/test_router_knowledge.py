"""Unit tests for api/routers/knowledge.py — RAG chat, knowledge index, chat history."""
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Must stub api.rag_chain before the knowledge router is imported
_rag_chain_stub = MagicMock()
_rag_chain_stub.build_rag_chain = MagicMock(return_value=lambda q: "mocked answer")
sys.modules["api.rag_chain"] = _rag_chain_stub
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.domain.exceptions import LlmUnavailableError
from api.routers.knowledge import router
from api.dependencies import get_db
from api.limiter import limiter

_app = FastAPI()
_app.state.limiter = limiter
_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
_app.include_router(router)


def _mock_note(**kwargs):
    note = MagicMock()
    note.id = kwargs.get("id", 1)
    note.session_id = kwargs.get("session_id", "sess-abc")
    note.question = kwargs.get("question", "Hva er risikoen?")
    note.answer = kwargs.get("answer", "Lav risiko.")
    note.created_at = kwargs.get("created_at", "2026-01-01T10:00:00")
    return note


def _mock_chunk(**kwargs):
    chunk = MagicMock()
    chunk.id = kwargs.get("id", 1)
    chunk.orgnr = kwargs.get("orgnr", "123456789")
    chunk.source = kwargs.get("source", "annual_report_2023")
    chunk.chunk_text = kwargs.get("chunk_text", "Omsetningen økte med 12% i 2023.")
    chunk.created_at = kwargs.get("created_at", "2026-01-01T10:00:00")
    return chunk


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def client(mock_db):
    _app.dependency_overrides[get_db] = lambda: mock_db
    yield TestClient(_app)
    _app.dependency_overrides.clear()


# ── POST /org/{orgnr}/ingest-knowledge ───────────────────────────────────────

def test_ingest_knowledge_returns_200(client):
    with patch("api.routers.knowledge._chunk_and_store", return_value=3):
        resp = client.post("/org/123456789/ingest-knowledge",
                           json={"text": "Some insurance text", "source": "custom"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["chunks_stored"] == 3
    assert body["orgnr"] == "123456789"


def test_ingest_knowledge_returns_422_when_empty_text(client):
    resp = client.post("/org/123456789/ingest-knowledge",
                       json={"text": "   ", "source": "custom"})
    assert resp.status_code == 422


def test_ingest_knowledge_returns_422_when_missing_text(client):
    resp = client.post("/org/123456789/ingest-knowledge", json={})
    assert resp.status_code == 422


# ── GET /knowledge ────────────────────────────────────────────────────────────

def test_search_knowledge_returns_200(client, mock_db):
    mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
    with patch("api.routers.knowledge._embed", return_value=None):
        resp = client.get("/knowledge?query=risiko")
    assert resp.status_code == 200


def test_search_knowledge_returns_chunks(client, mock_db):
    chunk = _mock_chunk(orgnr="123", source="annual_report_2023",
                        chunk_text="Long text about risk " * 10)
    mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = [chunk]
    with patch("api.routers.knowledge._embed", return_value=None):
        resp = client.get("/knowledge?query=risiko")
    items = resp.json()
    assert len(items) == 1
    assert items[0]["orgnr"] == "123"
    assert items[0]["source"] == "annual_report_2023"
    # chunk_text truncated to 400 chars
    assert len(items[0]["chunk_text"]) <= 400


def test_search_knowledge_returns_empty_list_when_no_results(client, mock_db):
    mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
    with patch("api.routers.knowledge._embed", return_value=None):
        resp = client.get("/knowledge?query=nothing")
    assert resp.json() == []


# ── GET /org/{orgnr}/chat ─────────────────────────────────────────────────────

def test_get_chat_history_returns_200(client, mock_db):
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    resp = client.get("/org/123456789/chat")
    assert resp.status_code == 200


def test_get_chat_history_returns_notes(client, mock_db):
    note = _mock_note(id=3, question="Q?", answer="A.")
    q = mock_db.query.return_value
    q.filter.return_value = q
    q.order_by.return_value.limit.return_value.all.return_value = [note]
    resp = client.get("/org/123456789/chat")
    items = resp.json()
    assert len(items) == 1
    assert items[0]["question"] == "Q?"
    assert items[0]["answer"] == "A."


def test_get_chat_history_returns_empty_when_no_notes(client, mock_db):
    q = mock_db.query.return_value
    q.filter.return_value = q
    q.order_by.return_value.limit.return_value.all.return_value = []
    resp = client.get("/org/123456789/chat")
    assert resp.json() == []


# ── DELETE /org/{orgnr}/chat ─────────────────────────────────────────────────

def test_delete_chat_session_returns_200(client):
    with patch("api.routers.knowledge._clear_chat_session", return_value=5):
        resp = client.delete("/org/123456789/chat?session_id=sess-abc")
    assert resp.status_code == 200
    body = resp.json()
    assert body["deleted"] == 5
    assert body["session_id"] == "sess-abc"


def test_delete_chat_session_returns_422_when_no_session_id(client):
    resp = client.delete("/org/123456789/chat")
    assert resp.status_code == 422


# ── POST /knowledge/index ─────────────────────────────────────────────────────

def test_trigger_knowledge_index_returns_200(client):
    index_result = {"docs_chunks": 10, "video_chunks": 5}
    stats = {"total_chunks": 15, "docs": 3}
    with patch("api.services.knowledge_index.index_all", return_value=index_result), \
         patch("api.services.knowledge_index.get_stats", return_value=stats):
        resp = client.post("/knowledge/index")
    assert resp.status_code == 200


def test_trigger_knowledge_index_returns_total_chunks(client):
    index_result = {"docs_chunks": 12, "video_chunks": 8}
    stats = {"total_chunks": 20}
    with patch("api.services.knowledge_index.index_all", return_value=index_result), \
         patch("api.services.knowledge_index.get_stats", return_value=stats):
        resp = client.post("/knowledge/index")
    assert resp.json()["total_new_chunks"] == 20


def test_trigger_knowledge_index_clears_when_force(client):
    index_result = {"docs_chunks": 0, "video_chunks": 0}
    stats = {"total_chunks": 0}
    with patch("api.services.knowledge_index.clear_knowledge", return_value=50) as mock_clear, \
         patch("api.services.knowledge_index.index_all", return_value=index_result), \
         patch("api.services.knowledge_index.get_stats", return_value=stats):
        resp = client.post("/knowledge/index?force=true")
    assert resp.status_code == 200
    mock_clear.assert_called_once()
    assert resp.json()["cleared_chunks"] == 50


# ── GET /knowledge/index/stats ────────────────────────────────────────────────

def test_knowledge_index_stats_returns_200(client):
    # Real get_stats returns total_chunks/doc_chunks/video_chunks
    stats = {"total_chunks": 42, "doc_chunks": 5, "video_chunks": 2}
    with patch("api.services.knowledge_index.get_stats", return_value=stats):
        resp = client.get("/knowledge/index/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_chunks"] == 42
    assert body["doc_chunks"] == 5
    assert body["video_chunks"] == 2


# ── POST /knowledge/chat ──────────────────────────────────────────────────────

def test_knowledge_chat_returns_no_knowledge_message_when_no_chunks(client):
    with patch("api.routers.knowledge._retrieve_knowledge_chunks", return_value=[]):
        resp = client.post("/knowledge/chat", json={"question": "What is covered?"})
    assert resp.status_code == 200
    body = resp.json()
    assert "Ingen kunnskap" in body["answer"]
    assert body["sources"] == []


def test_knowledge_chat_returns_answer_with_chunks(client):
    chunks = [{"text": "Ansvarsforsikring dekker skader på tredjepart.",
               "source": "doc::category::Policy Title"}]
    with patch("api.routers.knowledge._retrieve_knowledge_chunks", return_value=chunks), \
         patch("api.routers.knowledge._llm_answer_raw", return_value="Ja, ansvar dekkes."):
        resp = client.post("/knowledge/chat", json={"question": "Hva dekkes?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "Ja, ansvar dekkes."
    assert len(body["sources"]) == 1


def test_knowledge_chat_returns_503_when_llm_unavailable(client):
    chunks = [{"text": "some text", "source": "doc::x::y"}]
    with patch("api.routers.knowledge._retrieve_knowledge_chunks", return_value=chunks), \
         patch("api.routers.knowledge._llm_answer_raw",
               side_effect=LlmUnavailableError("no key")):
        resp = client.post("/knowledge/chat", json={"question": "?"})
    assert resp.status_code == 503
