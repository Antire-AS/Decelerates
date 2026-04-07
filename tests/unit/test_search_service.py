"""Unit tests for api/services/search_service.py — SearchService.

All Azure SDK calls are mocked; conftest.py already stubs azure.search.documents.
"""
import os
from unittest.mock import MagicMock, patch


from api.services.search_service import (
    SearchService,
    _get_index_name,
    _is_configured,
)


# ── _is_configured ────────────────────────────────────────────────────────────

def test_is_configured_returns_true_when_both_set():
    env = {
        "AZURE_SEARCH_ENDPOINT": "https://real.search.windows.net",
        "AZURE_SEARCH_API_KEY": "real-api-key",
    }
    with patch.dict(os.environ, env, clear=False):
        assert _is_configured() is True


def test_is_configured_returns_false_when_endpoint_missing():
    env = {"AZURE_SEARCH_ENDPOINT": "", "AZURE_SEARCH_API_KEY": "key"}
    with patch.dict(os.environ, env, clear=False):
        assert _is_configured() is False


def test_is_configured_returns_false_when_key_missing():
    env = {"AZURE_SEARCH_ENDPOINT": "https://real.search.windows.net", "AZURE_SEARCH_API_KEY": ""}
    with patch.dict(os.environ, env, clear=False):
        assert _is_configured() is False


def test_is_configured_returns_false_when_endpoint_is_placeholder():
    env = {"AZURE_SEARCH_ENDPOINT": "your_endpoint_here", "AZURE_SEARCH_API_KEY": "key"}
    with patch.dict(os.environ, env, clear=False):
        assert _is_configured() is False


def test_is_configured_returns_false_when_key_is_placeholder():
    env = {"AZURE_SEARCH_ENDPOINT": "https://real.search.windows.net", "AZURE_SEARCH_API_KEY": "your_key_here"}
    with patch.dict(os.environ, env, clear=False):
        assert _is_configured() is False


# ── _get_index_name ───────────────────────────────────────────────────────────

def test_get_index_name_returns_env_value_when_set():
    with patch.dict(os.environ, {"AZURE_SEARCH_INDEX_NAME": "my-custom-index"}, clear=False):
        assert _get_index_name() == "my-custom-index"


def test_get_index_name_returns_default_when_not_set():
    env_without_key = {k: v for k, v in os.environ.items() if k != "AZURE_SEARCH_INDEX_NAME"}
    with patch.dict(os.environ, env_without_key, clear=True):
        assert _get_index_name() == "company-chunks"


# ── SearchService.is_configured ───────────────────────────────────────────────

def test_search_service_is_configured_delegates_to_module_function():
    with patch("api.services.search_service._is_configured", return_value=True):
        assert SearchService().is_configured() is True
    with patch("api.services.search_service._is_configured", return_value=False):
        assert SearchService().is_configured() is False


# ── SearchService.index_chunk ─────────────────────────────────────────────────

def test_index_chunk_returns_empty_string_when_not_configured():
    with patch("api.services.search_service._is_configured", return_value=False):
        result = SearchService().index_chunk("123", "source", "text", [0.1, 0.2])
    assert result == ""


def test_index_chunk_uploads_document_and_returns_uuid():
    mock_client = MagicMock()
    with patch("api.services.search_service._is_configured", return_value=True):
        with patch.object(SearchService, "_search_client", return_value=mock_client):
            result = SearchService().index_chunk("123", "doc::1", "chunk text", [0.1, 0.2])
    assert result != ""
    mock_client.upload_documents.assert_called_once()
    uploaded = mock_client.upload_documents.call_args[1]["documents"][0]
    assert uploaded["orgnr"] == "123"
    assert uploaded["source"] == "doc::1"
    assert uploaded["chunk_text"] == "chunk text"


def test_index_chunk_returns_empty_string_on_exception():
    mock_client = MagicMock()
    mock_client.upload_documents.side_effect = Exception("upload failed")
    with patch("api.services.search_service._is_configured", return_value=True):
        with patch.object(SearchService, "_search_client", return_value=mock_client):
            result = SearchService().index_chunk("123", "src", "text", [0.1])
    assert result == ""


def test_index_chunk_uses_empty_list_when_embedding_is_none():
    mock_client = MagicMock()
    with patch("api.services.search_service._is_configured", return_value=True):
        with patch.object(SearchService, "_search_client", return_value=mock_client):
            SearchService().index_chunk("123", "src", "text", None)
    uploaded = mock_client.upload_documents.call_args[1]["documents"][0]
    assert uploaded["embedding"] == []


# ── SearchService.search_chunks ───────────────────────────────────────────────

def test_search_chunks_returns_empty_list_when_not_configured():
    with patch("api.services.search_service._is_configured", return_value=False):
        result = SearchService().search_chunks("123", [0.1, 0.2], 5)
    assert result == []


def test_search_chunks_returns_chunk_texts():
    mock_client = MagicMock()
    mock_client.search.return_value = [
        {"chunk_text": "First relevant chunk"},
        {"chunk_text": "Second relevant chunk"},
    ]
    with patch("api.services.search_service._is_configured", return_value=True):
        with patch.object(SearchService, "_search_client", return_value=mock_client):
            result = SearchService().search_chunks("123", [0.1, 0.2], 5)
    assert result == ["First relevant chunk", "Second relevant chunk"]


def test_search_chunks_skips_results_without_chunk_text():
    mock_client = MagicMock()
    mock_client.search.return_value = [
        {"chunk_text": "Valid chunk"},
        {"chunk_text": None},
        {},
    ]
    with patch("api.services.search_service._is_configured", return_value=True):
        with patch.object(SearchService, "_search_client", return_value=mock_client):
            result = SearchService().search_chunks("123", [0.1], 5)
    assert result == ["Valid chunk"]


def test_search_chunks_returns_empty_list_on_exception():
    mock_client = MagicMock()
    mock_client.search.side_effect = Exception("search failed")
    with patch("api.services.search_service._is_configured", return_value=True):
        with patch.object(SearchService, "_search_client", return_value=mock_client):
            result = SearchService().search_chunks("123", [0.1], 5)
    assert result == []


# ── SearchService.delete_chunks ───────────────────────────────────────────────

def test_delete_chunks_returns_zero_when_not_configured():
    with patch("api.services.search_service._is_configured", return_value=False):
        assert SearchService().delete_chunks("123") == 0


def test_delete_chunks_returns_zero_when_no_documents_found():
    mock_client = MagicMock()
    mock_client.search.return_value = []
    with patch("api.services.search_service._is_configured", return_value=True):
        with patch.object(SearchService, "_search_client", return_value=mock_client):
            result = SearchService().delete_chunks("123")
    assert result == 0
    mock_client.delete_documents.assert_not_called()


def test_delete_chunks_deletes_found_documents_and_returns_count():
    mock_client = MagicMock()
    mock_client.search.return_value = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    with patch("api.services.search_service._is_configured", return_value=True):
        with patch.object(SearchService, "_search_client", return_value=mock_client):
            result = SearchService().delete_chunks("123")
    assert result == 3
    mock_client.delete_documents.assert_called_once_with(documents=[{"id": "a"}, {"id": "b"}, {"id": "c"}])


def test_delete_chunks_returns_zero_on_exception():
    mock_client = MagicMock()
    mock_client.search.side_effect = Exception("search error")
    with patch("api.services.search_service._is_configured", return_value=True):
        with patch.object(SearchService, "_search_client", return_value=mock_client):
            result = SearchService().delete_chunks("123")
    assert result == 0


# ── SearchService.ensure_index ────────────────────────────────────────────────

def test_ensure_index_does_nothing_when_not_configured():
    with patch("api.services.search_service._is_configured", return_value=False):
        with patch.object(SearchService, "_index_client") as mock_index_client:
            SearchService().ensure_index()
    mock_index_client.assert_not_called()


def test_ensure_index_does_not_raise_when_exception_occurs():
    with patch("api.services.search_service._is_configured", return_value=True):
        with patch.object(SearchService, "_index_client", side_effect=Exception("Azure down")):
            # Should log warning but not propagate the exception
            SearchService().ensure_index()


def test_ensure_index_calls_get_index_when_configured():
    mock_client = MagicMock()
    with patch("api.services.search_service._is_configured", return_value=True):
        with patch.object(SearchService, "_index_client", return_value=mock_client):
            SearchService().ensure_index()
    mock_client.get_index.assert_called_once()
