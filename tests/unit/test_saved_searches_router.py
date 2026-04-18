"""Unit tests for api/routers/saved_searches.py.

Calls endpoint functions directly with mocked service + db + user. The
SavedSearchService itself has its own test suite (test_saved_search_service.py).
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from api.domain.exceptions import NotFoundError
from api.routers.saved_searches import (
    _resolve_user_id,
    _serialize,
    create_saved_search,
    delete_saved_search,
    list_saved_searches,
)


def _user(oid="azure-oid-123", email="broker@test.no"):
    return SimpleNamespace(oid=oid, email=email)


def _saved_search_row(id=1, user_id=42, name="High risk Oslo"):
    r = MagicMock()
    r.id = id
    r.user_id = user_id
    r.name = name
    r.params = {"kommune": "Oslo", "min_risk": 5}
    r.created_at = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    return r


# ── _resolve_user_id ──────────────────────────────────────────────────────────


def test_resolve_user_id_returns_id_when_user_exists():
    db = MagicMock()
    user_row = MagicMock(id=42)
    db.query.return_value.filter.return_value.first.return_value = user_row
    result = _resolve_user_id(db, _user())
    assert result == 42


def test_resolve_user_id_raises_404_when_user_missing():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(HTTPException) as exc:
        _resolve_user_id(db, _user())
    assert exc.value.status_code == 404
    assert "User record not found" in str(exc.value.detail)


# ── _serialize ────────────────────────────────────────────────────────────────


def test_serialize_returns_dict():
    row = _saved_search_row()
    result = _serialize(row)
    assert result["id"] == 1
    assert result["user_id"] == 42
    assert result["name"] == "High risk Oslo"
    assert result["params"] == {"kommune": "Oslo", "min_risk": 5}
    assert result["created_at"] == datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


# ── list_saved_searches ───────────────────────────────────────────────────────


def test_list_returns_serialized_user_searches():
    db = MagicMock()
    user_row = MagicMock(id=42)
    db.query.return_value.filter.return_value.first.return_value = user_row
    svc = MagicMock()
    svc.list_for_user.return_value = [_saved_search_row(id=1), _saved_search_row(id=2)]

    result = list_saved_searches(db=db, svc=svc, user=_user())

    assert len(result) == 2
    svc.list_for_user.assert_called_once_with(42)


def test_list_returns_empty_when_no_searches():
    db = MagicMock()
    user_row = MagicMock(id=42)
    db.query.return_value.filter.return_value.first.return_value = user_row
    svc = MagicMock()
    svc.list_for_user.return_value = []

    result = list_saved_searches(db=db, svc=svc, user=_user())
    assert result == []


# ── create_saved_search ───────────────────────────────────────────────────────


def test_create_calls_service_with_user_id():
    db = MagicMock()
    user_row = MagicMock(id=42)
    db.query.return_value.filter.return_value.first.return_value = user_row
    svc = MagicMock()
    svc.create.return_value = _saved_search_row(id=99)

    body = MagicMock()
    body.name = "New search"
    body.params = {"kommune": "Bergen"}

    result = create_saved_search(body=body, db=db, svc=svc, user=_user())

    assert result["id"] == 99
    svc.create.assert_called_once_with(42, "New search", {"kommune": "Bergen"})


# ── delete_saved_search ───────────────────────────────────────────────────────


def test_delete_calls_service_with_user_id():
    db = MagicMock()
    user_row = MagicMock(id=42)
    db.query.return_value.filter.return_value.first.return_value = user_row
    svc = MagicMock()

    delete_saved_search(search_id=7, db=db, svc=svc, user=_user())

    svc.delete.assert_called_once_with(7, 42)


def test_delete_raises_404_when_service_raises_not_found():
    db = MagicMock()
    user_row = MagicMock(id=42)
    db.query.return_value.filter.return_value.first.return_value = user_row
    svc = MagicMock()
    svc.delete.side_effect = NotFoundError("Saved search 999 not found")

    with pytest.raises(HTTPException) as exc:
        delete_saved_search(search_id=999, db=db, svc=svc, user=_user())
    assert exc.value.status_code == 404
