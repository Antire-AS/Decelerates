"""Unit tests for api/services/rag.py — RagService + helpers.

Pure static tests — uses MagicMock DB; no real infrastructure required.
api.rag_chain is stubbed before import to avoid langchain dependency.
"""

import sys
from unittest.mock import MagicMock, patch


# Stub api.rag_chain before importing rag.py to avoid langchain at import time.
_rag_chain_stub = MagicMock()
_rag_chain_stub.chunk_text = MagicMock(return_value=["chunk1"])
_rag_chain_stub.embed_chunks = MagicMock(return_value=[("chunk1", "src", [0.1, 0.2])])
if "api.rag_chain" not in sys.modules:
    sys.modules["api.rag_chain"] = _rag_chain_stub

from api.services.rag import (
    RagService,
    _build_company_context,
    _chunk_and_store,
    _retrieve_chunks,
    _save_to_rag,
    clear_chat_session,
    save_qa_note,
)


def _mock_db():
    return MagicMock()


def _mock_company(**kwargs):
    c = MagicMock()
    c.navn = kwargs.get("navn", "Test AS")
    c.orgnr = kwargs.get("orgnr", "123456789")
    c.organisasjonsform_kode = kwargs.get("kode", "AS")
    c.kommune = kwargs.get("kommune", "Oslo")
    c.land = kwargs.get("land", "Norge")
    c.naeringskode1 = kwargs.get("naeringskode1", "62.010")
    c.naeringskode1_beskrivelse = kwargs.get("desc", "IT-tjenester")
    c.pep_raw = kwargs.get("pep_raw", {})
    c.regnskapsår = kwargs.get("regnskapsår", None)
    return c


# ── _build_company_context ────────────────────────────────────────────────────


def test_build_company_context_includes_company_name_and_orgnr():
    company = _mock_company(navn="Firma AS", orgnr="123456789")
    result = _build_company_context(company, [])
    assert "Firma AS" in result
    assert "123456789" in result


def test_build_company_context_includes_municipality():
    company = _mock_company(kommune="Bergen", land="Norge")
    result = _build_company_context(company, [])
    assert "Bergen" in result


def test_build_company_context_includes_financial_data_when_set():
    company = _mock_company(regnskapsår=2023)
    company.equity_ratio = 0.35
    company.sum_driftsinntekter = 1_000_000
    company.sum_egenkapital = 500_000
    company.sum_eiendeler = 1_500_000
    company.risk_score = 3
    company.regnskap_raw = {}
    result = _build_company_context(company, [])
    assert "2023" in result
    assert "35.0%" in result


def test_build_company_context_includes_qa_notes():
    company = _mock_company(orgnr="111222333")
    note = MagicMock()
    note.orgnr = "111222333"
    note.created_at = "2024-01-15T10:00:00"
    note.question = "Hva er risikoen?"
    note.answer = "Risikoen er lav."
    result = _build_company_context(company, [note])
    assert "Hva er risikoen?" in result
    assert "Risikoen er lav." in result


def test_build_company_context_shows_pep_hit_count():
    company = _mock_company(pep_raw={"hit_count": 2})
    result = _build_company_context(company, [])
    assert "2" in result


def test_build_company_context_handles_none_equity_ratio():
    company = _mock_company(regnskapsår=2022)
    company.equity_ratio = None
    company.sum_driftsinntekter = 0
    company.sum_egenkapital = 0
    company.sum_eiendeler = 0
    company.risk_score = 1
    company.regnskap_raw = {}
    result = _build_company_context(company, [])
    assert "–" in result


# ── RagService.chunk_and_store ────────────────────────────────────────────────


@patch("api.services.rag.SearchService")
@patch(
    "api.services.rag.embed_chunks", return_value=[("chunk text", "source", [0.1, 0.2])]
)
@patch("api.services.rag.chunk_text", return_value=["chunk text"])
def test_chunk_and_store_returns_chunk_count(mock_chunk, mock_embed, mock_search_cls):
    mock_search_cls.return_value.is_configured.return_value = False
    db = _mock_db()
    count = RagService(db).chunk_and_store("123", "annual_report", "text content")
    assert count == 1


@patch("api.services.rag.SearchService")
@patch(
    "api.services.rag.embed_chunks",
    return_value=[("c1", "s", [0.1]), ("c2", "s", [0.2])],
)
@patch("api.services.rag.chunk_text", return_value=["c1", "c2"])
def test_chunk_and_store_adds_one_chunk_row_per_item(
    mock_chunk, mock_embed, mock_search_cls
):
    mock_search_cls.return_value.is_configured.return_value = False
    db = _mock_db()
    RagService(db).chunk_and_store("123", "src", "text")
    assert db.add.call_count == 2
    db.commit.assert_called_once()


@patch("api.services.rag.SearchService")
@patch("api.services.rag.embed_chunks", return_value=[("chunk", "src", [0.1, 0.2])])
@patch("api.services.rag.chunk_text", return_value=["chunk"])
def test_chunk_and_store_indexes_to_azure_search_when_configured(
    mock_chunk, mock_embed, mock_search_cls
):
    mock_search = MagicMock()
    mock_search.is_configured.return_value = True
    mock_search_cls.return_value = mock_search
    db = _mock_db()
    RagService(db).chunk_and_store("123", "src", "text")
    mock_search.index_chunk.assert_called_once()


@patch("api.services.rag.SearchService")
@patch("api.services.rag.embed_chunks", return_value=[])
@patch("api.services.rag.chunk_text", return_value=[])
def test_chunk_and_store_returns_zero_for_empty_text(
    mock_chunk, mock_embed, mock_search_cls
):
    mock_search_cls.return_value.is_configured.return_value = False
    db = _mock_db()
    count = RagService(db).chunk_and_store("123", "src", "")
    assert count == 0
    db.commit.assert_called_once()


@patch("api.services.rag.SearchService")
@patch("api.services.rag.embed_chunks", return_value=[("c", "s", None)])
@patch("api.services.rag.chunk_text", return_value=["c"])
def test_chunk_and_store_stores_none_embedding_when_vector_is_none(
    mock_chunk, mock_embed, mock_search_cls
):
    mock_search_cls.return_value.is_configured.return_value = False
    db = _mock_db()
    RagService(db).chunk_and_store("123", "src", "text")
    added = db.add.call_args[0][0]
    assert added.embedding is None


# ── RagService.retrieve_chunks ────────────────────────────────────────────────


@patch("api.services.rag.SearchService")
@patch("api.services.rag._embed", return_value=[0.1, 0.2])
def test_retrieve_chunks_uses_azure_search_when_configured(mock_embed, mock_search_cls):
    mock_search = MagicMock()
    mock_search.is_configured.return_value = True
    mock_search.search_chunks.return_value = ["chunk1", "chunk2"]
    mock_search_cls.return_value = mock_search
    db = _mock_db()
    result = RagService(db).retrieve_chunks("123", "question?")
    assert result == ["chunk1", "chunk2"]
    mock_search.search_chunks.assert_called_once()


@patch("api.services.rag.SearchService")
@patch("api.services.rag._embed", return_value=[0.1, 0.2])
def test_retrieve_chunks_falls_back_to_pgvector_when_search_not_configured(
    mock_embed, mock_search_cls
):
    mock_search_cls.return_value.is_configured.return_value = False
    mock_row = MagicMock()
    mock_row.chunk_text = "retrieved chunk"
    db = _mock_db()
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
        mock_row
    ]
    result = RagService(db).retrieve_chunks("123", "question?")
    assert "retrieved chunk" in result


@patch("api.services.rag.SearchService")
@patch("api.services.rag._embed", return_value=[0.1, 0.2])
def test_retrieve_chunks_falls_back_when_search_returns_empty(
    mock_embed, mock_search_cls
):
    mock_search = MagicMock()
    mock_search.is_configured.return_value = True
    mock_search.search_chunks.return_value = []
    mock_search_cls.return_value = mock_search
    mock_row = MagicMock()
    mock_row.chunk_text = "pgvector chunk"
    db = _mock_db()
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
        mock_row
    ]
    result = RagService(db).retrieve_chunks("123", "question?")
    assert "pgvector chunk" in result


# ── RagService._pgvector_retrieve ─────────────────────────────────────────────


def test_pgvector_retrieve_without_embedding_orders_by_id():
    mock_row = MagicMock()
    mock_row.chunk_text = "fallback chunk"
    db = _mock_db()
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
        mock_row
    ]
    result = RagService(db)._pgvector_retrieve("123", None, 5)
    assert result == ["fallback chunk"]


# ── RagService.save_qa_note ───────────────────────────────────────────────────


@patch("api.services.rag._embed", return_value=[0.1, 0.2, 0.3])
def test_save_qa_note_adds_and_commits(mock_embed):
    db = _mock_db()
    RagService(db).save_qa_note("123", "Q?", "Answer.")
    db.add.assert_called_once()
    db.commit.assert_called_once()


@patch("api.services.rag._embed", return_value=[0.1, 0.2])
def test_save_qa_note_sets_fields_correctly(mock_embed):
    db = _mock_db()
    RagService(db).save_qa_note(
        "123456789", "What is X?", "X is Y.", session_id="sess1"
    )
    added = db.add.call_args[0][0]
    assert added.orgnr == "123456789"
    assert added.question == "What is X?"
    assert added.answer == "X is Y."
    assert added.session_id == "sess1"


@patch("api.services.rag._embed", return_value=None)
def test_save_qa_note_stores_none_embedding_when_embed_fails(mock_embed):
    db = _mock_db()
    RagService(db).save_qa_note("123", "Q?", "A.")
    added = db.add.call_args[0][0]
    assert added.embedding is None


@patch("api.services.rag._embed", return_value=[0.5])
def test_save_qa_note_session_id_none_when_not_provided(mock_embed):
    db = _mock_db()
    RagService(db).save_qa_note("123", "Q?", "A.")
    added = db.add.call_args[0][0]
    assert added.session_id is None


# ── RagService.save_to_rag ────────────────────────────────────────────────────


@patch("api.services.rag._embed", return_value=[0.1, 0.2])
def test_save_to_rag_adds_and_commits(mock_embed):
    db = _mock_db()
    RagService(db).save_to_rag("123", "Risk narrative", "Content here")
    db.add.assert_called_once()
    db.commit.assert_called_once()


@patch("api.services.rag._embed", return_value=[0.1])
def test_save_to_rag_sets_question_as_label(mock_embed):
    db = _mock_db()
    RagService(db).save_to_rag("123", "My Label", "Content")
    added = db.add.call_args[0][0]
    assert added.question == "My Label"
    assert added.answer == "Content"


@patch("api.services.rag._embed", side_effect=RuntimeError("embed failed"))
def test_save_to_rag_swallows_exceptions(mock_embed):
    db = _mock_db()
    # Should not raise even if _embed throws
    RagService(db).save_to_rag("123", "label", "content")


# ── Module-level backward-compat wrappers ─────────────────────────────────────


@patch("api.services.rag.SearchService")
@patch("api.services.rag.embed_chunks", return_value=[])
@patch("api.services.rag.chunk_text", return_value=[])
def test_chunk_and_store_wrapper_delegates(mock_chunk, mock_embed, mock_search_cls):
    mock_search_cls.return_value.is_configured.return_value = False
    db = _mock_db()
    count = _chunk_and_store("123", "src", "text", db)
    assert count == 0


@patch("api.services.rag.SearchService")
@patch("api.services.rag._embed", return_value=None)
def test_retrieve_chunks_wrapper_delegates(mock_embed, mock_search_cls):
    mock_search_cls.return_value.is_configured.return_value = False
    db = _mock_db()
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    result = _retrieve_chunks("123", "q?", db)
    assert result == []


@patch("api.services.rag._embed", return_value=[0.1])
def test_save_qa_note_wrapper_delegates(mock_embed):
    db = _mock_db()
    save_qa_note("123", "Q?", "A.", db, session_id="s1")
    db.add.assert_called_once()


@patch("api.services.rag._embed", return_value=[0.1])
def test_save_to_rag_wrapper_delegates(mock_embed):
    db = _mock_db()
    _save_to_rag("123", "label", "content", db)
    db.add.assert_called_once()


# ── clear_chat_session ────────────────────────────────────────────────────────


def test_clear_chat_session_returns_deleted_count():
    db = _mock_db()
    db.query.return_value.filter.return_value.delete.return_value = 4
    count = clear_chat_session("123", "sess-abc", db)
    assert count == 4
    db.commit.assert_called_once()


def test_clear_chat_session_returns_zero_when_none():
    db = _mock_db()
    db.query.return_value.filter.return_value.delete.return_value = 0
    count = clear_chat_session("123", "unknown-session", db)
    assert count == 0
