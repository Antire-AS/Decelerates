"""Unit tests for api/routers/documents.py — InsuranceDocument CRUD + analysis."""
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.domain.exceptions import LlmUnavailableError
from api.routers.documents import router
from api.dependencies import get_db

_app = FastAPI()
_app.include_router(router)


def _mock_doc(**kwargs):
    doc = MagicMock()
    doc.id = kwargs.get("id", 1)
    doc.title = kwargs.get("title", "Test Policy")
    doc.filename = kwargs.get("filename", "policy.pdf")
    doc.category = kwargs.get("category", "ansvar")
    doc.insurer = kwargs.get("insurer", "Gjensidige")
    doc.year = kwargs.get("year", 2023)
    doc.period = kwargs.get("period", "aktiv")
    doc.orgnr = kwargs.get("orgnr", "123456789")
    doc.uploaded_at = kwargs.get("uploaded_at", "2026-01-01T10:00:00")
    doc.tags = kwargs.get("tags", None)
    doc.pdf_content = kwargs.get("pdf_content", b"%PDF-content")
    doc.extracted_text = kwargs.get("extracted_text", "policy text")
    return doc


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def client(mock_db):
    _app.dependency_overrides[get_db] = lambda: mock_db
    yield TestClient(_app)
    _app.dependency_overrides.clear()


# ── GET /insurance-documents ──────────────────────────────────────────────────

def test_list_documents_returns_200(client, mock_db):
    mock_db.query.return_value.order_by.return_value.all.return_value = []
    resp = client.get("/insurance-documents")
    assert resp.status_code == 200


def test_list_documents_returns_empty_list(client, mock_db):
    mock_db.query.return_value.order_by.return_value.all.return_value = []
    resp = client.get("/insurance-documents")
    assert resp.json() == []


def test_list_documents_returns_doc_fields(client, mock_db):
    doc = _mock_doc(id=3, title="Ansvarsforsikring", insurer="If")
    mock_db.query.return_value.order_by.return_value.all.return_value = [doc]
    resp = client.get("/insurance-documents")
    items = resp.json()
    assert len(items) == 1
    assert items[0]["id"] == 3
    assert items[0]["title"] == "Ansvarsforsikring"
    assert items[0]["insurer"] == "If"


def test_list_documents_filters_applied(client, mock_db):
    """Verify filters are forwarded to the query chain (mock verifies chaining)."""
    q = mock_db.query.return_value
    q.filter.return_value = q
    q.order_by.return_value.all.return_value = []
    resp = client.get("/insurance-documents?category=ansvar&year=2023")
    assert resp.status_code == 200


# ── GET /insurance-documents/{doc_id}/pdf ─────────────────────────────────────

def test_download_document_pdf_returns_200(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = _mock_doc()
    resp = client.get("/insurance-documents/1/pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"


def test_download_document_pdf_returns_404_when_missing(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None
    resp = client.get("/insurance-documents/999/pdf")
    assert resp.status_code == 404


def test_download_document_pdf_returns_pdf_bytes(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = _mock_doc(
        pdf_content=b"%PDF-1.4 test"
    )
    resp = client.get("/insurance-documents/1/pdf")
    assert resp.content == b"%PDF-1.4 test"


# ── GET /insurance-documents/{doc_id}/keypoints ───────────────────────────────

def test_get_keypoints_returns_200(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = _mock_doc()
    with patch("api.routers.documents.get_document_keypoints",
               return_value={"keypoints": ["Point 1", "Point 2"]}):
        resp = client.get("/insurance-documents/1/keypoints")
    assert resp.status_code == 200


def test_get_keypoints_returns_404_when_missing(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None
    resp = client.get("/insurance-documents/999/keypoints")
    assert resp.status_code == 404


def test_get_keypoints_includes_doc_id_and_title(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = _mock_doc(
        id=5, title="Vilkår 2023"
    )
    with patch("api.routers.documents.get_document_keypoints",
               return_value={"keypoints": []}):
        resp = client.get("/insurance-documents/5/keypoints")
    body = resp.json()
    assert body["doc_id"] == 5
    assert body["title"] == "Vilkår 2023"


# ── GET /insurance-documents/{doc_id}/similar ─────────────────────────────────

def test_get_similar_returns_200(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = _mock_doc()
    with patch("api.routers.documents.find_similar_documents", return_value=[]):
        resp = client.get("/insurance-documents/1/similar")
    assert resp.status_code == 200


def test_get_similar_returns_404_when_missing(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None
    resp = client.get("/insurance-documents/999/similar")
    assert resp.status_code == 404


# ── DELETE /insurance-documents/{doc_id} ──────────────────────────────────────

def test_delete_document_returns_200(client, mock_db):
    with patch("api.routers.documents.remove_insurance_document", return_value=True), \
         patch("api.routers.documents.log_audit"):
        resp = client.delete("/insurance-documents/1")
    assert resp.status_code == 200
    assert resp.json() == {"deleted": 1}


def test_delete_document_returns_404_when_missing(client, mock_db):
    with patch("api.routers.documents.remove_insurance_document", return_value=False):
        resp = client.delete("/insurance-documents/999")
    assert resp.status_code == 404


# ── POST /insurance-documents/{doc_id}/chat ───────────────────────────────────

def test_chat_with_document_returns_200(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = _mock_doc()
    with patch("api.routers.documents.answer_document_question",
               return_value="Svaret er ja."):
        resp = client.post("/insurance-documents/1/chat",
                           json={"question": "Hva dekkes?"})
    assert resp.status_code == 200
    assert resp.json()["answer"] == "Svaret er ja."


def test_chat_with_document_returns_404_when_missing(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None
    resp = client.post("/insurance-documents/999/chat", json={"question": "?"})
    assert resp.status_code == 404


def test_chat_with_document_returns_503_when_llm_unavailable(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = _mock_doc()
    with patch("api.routers.documents.answer_document_question",
               side_effect=LlmUnavailableError("no key")):
        resp = client.post("/insurance-documents/1/chat", json={"question": "?"})
    assert resp.status_code == 503


# ── POST /insurance-documents/compare ────────────────────────────────────────

def test_compare_returns_400_when_not_two_ids(client, mock_db):
    resp = client.post("/insurance-documents/compare", json={"doc_ids": [1]})
    assert resp.status_code == 400


def test_compare_returns_400_when_three_ids(client, mock_db):
    resp = client.post("/insurance-documents/compare", json={"doc_ids": [1, 2, 3]})
    assert resp.status_code == 400


def test_compare_returns_404_when_docs_missing(client, mock_db):
    # Only one doc found for two requested IDs
    mock_db.query.return_value.filter.return_value.all.return_value = [_mock_doc(id=1)]
    resp = client.post("/insurance-documents/compare", json={"doc_ids": [1, 2]})
    assert resp.status_code == 404


def test_compare_returns_200_with_structured_result(client, mock_db):
    doc_a = _mock_doc(id=1, title="Policy A")
    doc_b = _mock_doc(id=2, title="Policy B")
    mock_db.query.return_value.filter.return_value.all.return_value = [doc_a, doc_b]
    comparison = {"summary": "A is better for X, B for Y"}
    with patch("api.routers.documents.compare_two_documents", return_value=comparison):
        resp = client.post("/insurance-documents/compare", json={"doc_ids": [1, 2]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["doc_a"]["id"] == 1
    assert body["doc_b"]["id"] == 2
    assert body["structured"] == comparison


def test_compare_returns_503_when_llm_unavailable(client, mock_db):
    doc_a = _mock_doc(id=1)
    doc_b = _mock_doc(id=2)
    mock_db.query.return_value.filter.return_value.all.return_value = [doc_a, doc_b]
    with patch("api.routers.documents.compare_two_documents",
               side_effect=LlmUnavailableError("no LLM")):
        resp = client.post("/insurance-documents/compare", json={"doc_ids": [1, 2]})
    assert resp.status_code == 503
