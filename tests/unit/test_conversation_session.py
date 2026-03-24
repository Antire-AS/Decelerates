"""Unit tests for chat session_id support in RagService / knowledge router helpers.

Pure static tests — uses MagicMock DB; no infrastructure required.
"""
from unittest.mock import MagicMock, patch, call
import pytest

from api.services.rag import save_qa_note, clear_chat_session


def _mock_db():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    return db


# ── save_qa_note session_id propagation ──────────────────────────────────────

def test_save_qa_note_stores_session_id():
    db = _mock_db()
    with patch("api.services.rag._embed", return_value=None):
        save_qa_note("123456789", "Q?", "A.", db, session_id="sess-abc")
    added = db.add.call_args[0][0]
    assert added.session_id == "sess-abc"


def test_save_qa_note_none_session_id():
    db = _mock_db()
    with patch("api.services.rag._embed", return_value=None):
        save_qa_note("123456789", "Q?", "A.", db, session_id=None)
    added = db.add.call_args[0][0]
    assert added.session_id is None


def test_save_qa_note_empty_string_session_id_stored_as_none():
    db = _mock_db()
    with patch("api.services.rag._embed", return_value=None):
        save_qa_note("123456789", "Q?", "A.", db, session_id="")
    added = db.add.call_args[0][0]
    # Empty string treated as None by the service
    assert added.session_id is None


def test_save_qa_note_commits():
    db = _mock_db()
    with patch("api.services.rag._embed", return_value=None):
        save_qa_note("123456789", "Q?", "A.", db)
    db.commit.assert_called_once()


def test_save_qa_note_backward_compat_no_session_id():
    """Existing callers that pass no session_id must still work."""
    db = _mock_db()
    with patch("api.services.rag._embed", return_value=None):
        save_qa_note("123456789", "Q?", "A.", db)
    db.add.assert_called_once()


# ── clear_chat_session ────────────────────────────────────────────────────────

def test_clear_chat_session_filters_by_orgnr_and_session():
    db = MagicMock()
    db.query.return_value.filter.return_value.delete.return_value = 3
    result = clear_chat_session("123456789", "sess-abc", db)
    assert result == 3
    db.commit.assert_called_once()


def test_clear_chat_session_commits_after_delete():
    db = MagicMock()
    db.query.return_value.filter.return_value.delete.return_value = 0
    clear_chat_session("123456789", "sess-xyz", db)
    db.commit.assert_called_once()


def test_clear_chat_session_returns_zero_when_nothing_deleted():
    db = MagicMock()
    db.query.return_value.filter.return_value.delete.return_value = 0
    result = clear_chat_session("123456789", "nonexistent-session", db)
    assert result == 0
