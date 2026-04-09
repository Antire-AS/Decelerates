"""Unit tests for api/services/saved_search_service.py.

Pure mock-based tests — no real DB session needed.
"""
from unittest.mock import MagicMock

import pytest

from api.domain.exceptions import NotFoundError
from api.services.saved_search_service import SavedSearchService


def _mock_db():
    db = MagicMock()
    return db


def _mock_query_chain(return_value):
    """Build a fluent SQLAlchemy query mock that returns *return_value* at the end."""
    chain = MagicMock()
    chain.filter.return_value = chain
    chain.order_by.return_value = chain
    chain.all.return_value = return_value
    chain.first.return_value = return_value
    return chain


# ── list_for_user ─────────────────────────────────────────────────────────────

def test_list_for_user_returns_query_results():
    db = _mock_db()
    expected = [MagicMock(id=1), MagicMock(id=2)]
    db.query.return_value = _mock_query_chain(expected)

    svc = SavedSearchService(db)
    result = svc.list_for_user(user_id=42)

    assert result == expected
    db.query.assert_called_once()


def test_list_for_user_returns_empty_when_none_exist():
    db = _mock_db()
    db.query.return_value = _mock_query_chain([])

    svc = SavedSearchService(db)
    result = svc.list_for_user(user_id=42)

    assert result == []


# ── create ────────────────────────────────────────────────────────────────────

def test_create_persists_and_returns_row():
    db = _mock_db()
    svc = SavedSearchService(db)

    row = svc.create(user_id=42, name="High risk Oslo", params={"kommune": "Oslo"})

    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(row)
    assert row.user_id == 42
    assert row.name == "High risk Oslo"
    assert row.params == {"kommune": "Oslo"}
    assert row.created_at is not None


def test_create_rolls_back_on_commit_failure():
    db = _mock_db()
    db.commit.side_effect = RuntimeError("connection lost")
    svc = SavedSearchService(db)

    with pytest.raises(RuntimeError, match="connection lost"):
        svc.create(user_id=1, name="x", params={})

    db.rollback.assert_called_once()


# ── delete ────────────────────────────────────────────────────────────────────

def test_delete_removes_row_when_found():
    db = _mock_db()
    row = MagicMock(id=7, user_id=42)
    db.query.return_value = _mock_query_chain(row)

    svc = SavedSearchService(db)
    svc.delete(search_id=7, user_id=42)

    db.delete.assert_called_once_with(row)
    db.commit.assert_called_once()


def test_delete_raises_not_found_when_missing():
    db = _mock_db()
    db.query.return_value = _mock_query_chain(None)

    svc = SavedSearchService(db)
    with pytest.raises(NotFoundError, match="Saved search 999 not found"):
        svc.delete(search_id=999, user_id=42)

    db.delete.assert_not_called()
    db.commit.assert_not_called()


def test_delete_scopes_to_user_id():
    """If a row exists but belongs to a different user, the filter excludes it
    and the service raises NotFoundError instead of leaking existence."""
    db = _mock_db()
    db.query.return_value = _mock_query_chain(None)

    svc = SavedSearchService(db)
    with pytest.raises(NotFoundError):
        svc.delete(search_id=7, user_id=99)


def test_delete_rolls_back_on_commit_failure():
    db = _mock_db()
    row = MagicMock(id=7, user_id=42)
    db.query.return_value = _mock_query_chain(row)
    db.commit.side_effect = RuntimeError("disk full")

    svc = SavedSearchService(db)
    with pytest.raises(RuntimeError, match="disk full"):
        svc.delete(search_id=7, user_id=42)

    db.rollback.assert_called_once()
