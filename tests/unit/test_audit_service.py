"""Unit tests for api/services/audit.py — log_audit helper and retention helpers.

Pure static tests — uses MagicMock DB; no infrastructure required.
"""
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

from api.services.audit import log_audit, purge_old_audit_logs, get_audit_summary


def _mock_db():
    return MagicMock()


# ── Happy path ────────────────────────────────────────────────────────────────

def test_log_audit_calls_add_and_commit():
    db = _mock_db()
    log_audit(db, "test_action")
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_log_audit_stores_action():
    db = _mock_db()
    log_audit(db, "view_client_profile")
    entry = db.add.call_args[0][0]
    assert entry.action == "view_client_profile"


def test_log_audit_stores_orgnr():
    db = _mock_db()
    log_audit(db, "send_tilbud", orgnr="984851006")
    entry = db.add.call_args[0][0]
    assert entry.orgnr == "984851006"


def test_log_audit_stores_actor_email():
    db = _mock_db()
    log_audit(db, "create_client_token", actor_email="broker@firma.no")
    entry = db.add.call_args[0][0]
    assert entry.actor_email == "broker@firma.no"


def test_log_audit_serializes_detail_as_json():
    db = _mock_db()
    log_audit(db, "update_status", detail={"status": "accepted", "offer_id": 42})
    entry = db.add.call_args[0][0]
    parsed = json.loads(entry.detail)
    assert parsed["status"] == "accepted"
    assert parsed["offer_id"] == 42


def test_log_audit_none_detail_stores_none():
    db = _mock_db()
    log_audit(db, "view", detail=None)
    entry = db.add.call_args[0][0]
    assert entry.detail is None


def test_log_audit_sets_utc_timestamp():
    db = _mock_db()
    log_audit(db, "test")
    entry = db.add.call_args[0][0]
    assert isinstance(entry.created_at, datetime)
    assert entry.created_at.tzinfo is not None


def test_log_audit_timestamp_is_recent():
    db = _mock_db()
    before = datetime.now(timezone.utc)
    log_audit(db, "test")
    after = datetime.now(timezone.utc)
    entry = db.add.call_args[0][0]
    assert before <= entry.created_at <= after


# ── Error handling ────────────────────────────────────────────────────────────

def test_log_audit_swallows_db_add_exception():
    db = _mock_db()
    db.add.side_effect = Exception("DB unavailable")
    log_audit(db, "test_action")  # Must not raise
    db.rollback.assert_called_once()


def test_log_audit_swallows_db_commit_exception():
    db = _mock_db()
    db.commit.side_effect = Exception("commit failed")
    log_audit(db, "test_action")  # Must not raise
    db.rollback.assert_called_once()


def test_log_audit_rollback_on_exception():
    db = _mock_db()
    db.add.side_effect = RuntimeError("connection lost")
    log_audit(db, "test")
    db.rollback.assert_called_once()


# ── Optional args ─────────────────────────────────────────────────────────────

def test_log_audit_minimal_call():
    """Only action is required; all other args are optional."""
    db = _mock_db()
    log_audit(db, "ping")  # No orgnr, no actor, no detail
    entry = db.add.call_args[0][0]
    assert entry.action == "ping"
    assert entry.orgnr is None
    assert entry.actor_email is None
    assert entry.detail is None


def test_log_audit_nested_detail():
    db = _mock_db()
    detail = {"items": [1, 2, 3], "meta": {"key": "value"}}
    log_audit(db, "batch", detail=detail)
    entry = db.add.call_args[0][0]
    parsed = json.loads(entry.detail)
    assert parsed["items"] == [1, 2, 3]
    assert parsed["meta"]["key"] == "value"


# ── purge_old_audit_logs ──────────────────────────────────────────────────────

def test_purge_old_audit_logs_calls_delete_and_commit():
    db = _mock_db()
    db.query.return_value.filter.return_value.delete.return_value = 5
    result = purge_old_audit_logs(db)
    db.query.return_value.filter.return_value.delete.assert_called_once()
    db.commit.assert_called_once()
    assert result == 5


def test_purge_old_audit_logs_returns_zero_when_nothing_old():
    db = _mock_db()
    db.query.return_value.filter.return_value.delete.return_value = 0
    result = purge_old_audit_logs(db)
    assert result == 0


# ── get_audit_summary ─────────────────────────────────────────────────────────

def test_get_audit_summary_returns_by_action_dict():
    db = _mock_db()
    row1 = MagicMock()
    row1.action = "policy.create"
    row1.count = 10
    row2 = MagicMock()
    row2.action = "policy.delete"
    row2.count = 2
    db.query.return_value.group_by.return_value.order_by.return_value.all.return_value = [row1, row2]
    # For the orgnr subquery when firm_id is None
    result = get_audit_summary(db, firm_id=None)
    assert "by_action" in result
