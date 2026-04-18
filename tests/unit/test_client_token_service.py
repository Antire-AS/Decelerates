"""Unit tests for api/services/client_token_service.py.

Pure static tests — uses MagicMock DB; no infrastructure required.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock


from api.services.client_token_service import (
    _TOKEN_TTL_DAYS,
    create_token,
    get_or_create_active_token,
    list_active_tokens,
)


def _mock_db(existing_token=None):
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = existing_token
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
        [existing_token] if existing_token else []
    )
    db.refresh = MagicMock()
    return db


def _make_token_row(orgnr="123456789", days_left=15):
    row = MagicMock()
    row.orgnr = orgnr
    row.token = "existing_token_abc"
    row.label = "test"
    row.expires_at = datetime.now(timezone.utc) + timedelta(days=days_left)
    row.created_at = datetime.now(timezone.utc)
    return row


# ── _TOKEN_TTL_DAYS ───────────────────────────────────────────────────────────


def test_ttl_days_is_30():
    assert _TOKEN_TTL_DAYS == 30


# ── create_token ──────────────────────────────────────────────────────────────


def test_create_token_calls_add_and_commit():
    db = _mock_db()
    create_token("123456789", "test label", db)
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_create_token_calls_refresh():
    db = _mock_db()
    create_token("123456789", None, db)
    db.refresh.assert_called_once()


def test_create_token_sets_orgnr():
    db = _mock_db()
    create_token("984851006", None, db)
    added = db.add.call_args[0][0]
    assert added.orgnr == "984851006"


def test_create_token_sets_label():
    db = _mock_db()
    create_token("123456789", "Shared with CEO", db)
    added = db.add.call_args[0][0]
    assert added.label == "Shared with CEO"


def test_create_token_none_label():
    db = _mock_db()
    create_token("123456789", None, db)
    added = db.add.call_args[0][0]
    assert added.label is None


def test_create_token_expiry_is_30_days():
    db = _mock_db()
    before = datetime.now(timezone.utc)
    create_token("123456789", None, db)
    after = datetime.now(timezone.utc)
    added = db.add.call_args[0][0]
    expected_min = before + timedelta(days=_TOKEN_TTL_DAYS)
    expected_max = after + timedelta(days=_TOKEN_TTL_DAYS)
    assert expected_min <= added.expires_at <= expected_max


def test_create_token_token_is_urlsafe_string():
    db = _mock_db()
    create_token("123456789", None, db)
    added = db.add.call_args[0][0]
    # token_urlsafe(32) produces at least 32 characters of base64url
    assert isinstance(added.token, str)
    assert len(added.token) >= 32


def test_create_token_each_call_unique():
    tokens = set()
    for _ in range(20):
        db = _mock_db()
        create_token("123456789", None, db)
        added = db.add.call_args[0][0]
        tokens.add(added.token)
    assert len(tokens) == 20


# ── get_or_create_active_token ────────────────────────────────────────────────


def test_get_or_create_returns_existing_when_found():
    existing = _make_token_row()
    db = _mock_db(existing_token=existing)
    result = get_or_create_active_token("123456789", None, db)
    assert result is existing
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_get_or_create_creates_when_no_active_token():
    db = _mock_db(existing_token=None)
    get_or_create_active_token("123456789", "new label", db)
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_get_or_create_creates_with_correct_orgnr():
    db = _mock_db(existing_token=None)
    get_or_create_active_token("984851006", None, db)
    added = db.add.call_args[0][0]
    assert added.orgnr == "984851006"


# ── list_active_tokens ────────────────────────────────────────────────────────


def test_list_active_tokens_returns_list():
    existing = _make_token_row()
    db = _mock_db(existing_token=existing)
    result = list_active_tokens("123456789", db)
    assert isinstance(result, list)


def test_list_active_tokens_empty_when_none():
    db = _mock_db(existing_token=None)
    result = list_active_tokens("123456789", db)
    assert result == []
