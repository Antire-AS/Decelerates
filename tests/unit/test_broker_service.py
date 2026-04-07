"""Unit tests for api/services/broker.py — BrokerService.

Pure static tests — uses MagicMock DB; no infrastructure required.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from api.db import BrokerNote, BrokerSettings
from api.domain.exceptions import NotFoundError
from api.services.broker import BrokerService


# ── helpers ───────────────────────────────────────────────────────────────────

def _mock_db():
    return MagicMock()


def _mock_settings(**kwargs):
    s = MagicMock(spec=BrokerSettings)
    s.id            = 1
    s.firm_name     = kwargs.get("firm_name", "Broker AS")
    s.orgnr         = kwargs.get("orgnr", "987654321")
    s.address       = kwargs.get("address", "Brokerveien 1")
    s.contact_name  = kwargs.get("contact_name", "Ola Nordmann")
    s.contact_email = kwargs.get("contact_email", "ola@broker.no")
    s.contact_phone = kwargs.get("contact_phone", "12345678")
    s.updated_at    = kwargs.get("updated_at", None)
    return s


def _mock_note(**kwargs):
    n = MagicMock(spec=BrokerNote)
    n.id         = kwargs.get("id", 1)
    n.orgnr      = kwargs.get("orgnr", "123456789")
    n.text       = kwargs.get("text", "Test note")
    n.created_at = kwargs.get("created_at", "2026-01-01T00:00:00+00:00")
    return n


def _settings_in(**kwargs):
    return SimpleNamespace(
        firm_name     = kwargs.get("firm_name", "Broker AS"),
        orgnr         = kwargs.get("orgnr", "987654321"),
        address       = kwargs.get("address", "Brokerveien 1"),
        contact_name  = kwargs.get("contact_name", "Ola Nordmann"),
        contact_email = kwargs.get("contact_email", "ola@broker.no"),
        contact_phone = kwargs.get("contact_phone", "12345678"),
    )


def _note_body(text="Test note"):
    return SimpleNamespace(text=text)


# ── get_settings ──────────────────────────────────────────────────────────────

def test_get_settings_returns_row_when_exists():
    settings = _mock_settings()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = settings
    result = BrokerService(db).get_settings()
    assert result is settings


def test_get_settings_returns_none_when_not_set():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    result = BrokerService(db).get_settings()
    assert result is None


def test_get_settings_queries_id_1():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    BrokerService(db).get_settings()
    db.query.assert_called_once_with(BrokerSettings)


# ── save_settings — update path ───────────────────────────────────────────────

def test_save_settings_updates_existing_row():
    existing = _mock_settings()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = existing
    BrokerService(db).save_settings(_settings_in(firm_name="New Broker AS"))
    assert existing.firm_name == "New Broker AS"


def test_save_settings_update_commits():
    existing = _mock_settings()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = existing
    BrokerService(db).save_settings(_settings_in())
    db.commit.assert_called_once()


def test_save_settings_update_does_not_call_add():
    existing = _mock_settings()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = existing
    BrokerService(db).save_settings(_settings_in())
    db.add.assert_not_called()


def test_save_settings_update_sets_all_fields():
    existing = _mock_settings()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = existing
    body = _settings_in(
        firm_name="Updated AS",
        orgnr="111111111",
        address="Ny gate 2",
        contact_name="Kari",
        contact_email="kari@updated.no",
        contact_phone="99999999",
    )
    BrokerService(db).save_settings(body)
    assert existing.orgnr         == "111111111"
    assert existing.address       == "Ny gate 2"
    assert existing.contact_name  == "Kari"
    assert existing.contact_email == "kari@updated.no"
    assert existing.contact_phone == "99999999"


def test_save_settings_update_stamps_updated_at():
    existing = _mock_settings()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = existing
    BrokerService(db).save_settings(_settings_in())
    assert existing.updated_at is not None


def test_save_settings_update_returns_ok_status():
    existing = _mock_settings()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = existing
    result = BrokerService(db).save_settings(_settings_in())
    assert result["status"] == "ok"
    assert "updated_at" in result


# ── save_settings — insert path ───────────────────────────────────────────────

def test_save_settings_creates_row_when_none_exists():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    BrokerService(db).save_settings(_settings_in())
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_save_settings_insert_sets_id_1():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    BrokerService(db).save_settings(_settings_in())
    added = db.add.call_args[0][0]
    assert added.id == 1


def test_save_settings_insert_sets_firm_name():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    BrokerService(db).save_settings(_settings_in(firm_name="Fresh Broker AS"))
    added = db.add.call_args[0][0]
    assert added.firm_name == "Fresh Broker AS"


def test_save_settings_insert_returns_ok_status():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    result = BrokerService(db).save_settings(_settings_in())
    assert result["status"] == "ok"


# ── list_notes ────────────────────────────────────────────────────────────────

def test_list_notes_returns_notes_for_orgnr():
    notes = [_mock_note(), _mock_note(id=2)]
    db = _mock_db()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = notes
    result = BrokerService(db).list_notes("123456789")
    assert result == notes


def test_list_notes_returns_empty_list_when_none():
    db = _mock_db()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    result = BrokerService(db).list_notes("000000000")
    assert result == []


def test_list_notes_queries_broker_note():
    db = _mock_db()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    BrokerService(db).list_notes("123456789")
    db.query.assert_called_once_with(BrokerNote)


# ── create_note ───────────────────────────────────────────────────────────────

def test_create_note_adds_to_db_and_commits():
    db = _mock_db()
    BrokerService(db).create_note("123456789", _note_body("My note"))
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_create_note_strips_whitespace():
    db = _mock_db()
    BrokerService(db).create_note("123456789", _note_body("  padded note  "))
    added = db.add.call_args[0][0]
    assert added.text == "padded note"


def test_create_note_sets_orgnr():
    db = _mock_db()
    BrokerService(db).create_note("987654321", _note_body("note"))
    added = db.add.call_args[0][0]
    assert added.orgnr == "987654321"


def test_create_note_sets_created_at():
    db = _mock_db()
    BrokerService(db).create_note("123456789", _note_body("note"))
    added = db.add.call_args[0][0]
    assert added.created_at is not None


def test_create_note_returns_note():
    db = _mock_db()
    result = BrokerService(db).create_note("123456789", _note_body("note"))
    # After refresh, the added object is returned
    assert result is db.add.call_args[0][0]


def test_create_note_refreshes():
    db = _mock_db()
    BrokerService(db).create_note("123456789", _note_body("note"))
    db.refresh.assert_called_once()


# ── delete_note ───────────────────────────────────────────────────────────────

def test_delete_note_calls_db_delete_and_commits():
    note = _mock_note()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = note
    BrokerService(db).delete_note(1, "123456789")
    db.delete.assert_called_once_with(note)
    db.commit.assert_called_once()


def test_delete_note_raises_not_found_when_missing():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(NotFoundError, match="Note 99 not found"):
        BrokerService(db).delete_note(99, "123456789")


def test_delete_note_does_not_commit_when_not_found():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(NotFoundError):
        BrokerService(db).delete_note(99, "123456789")
    db.commit.assert_not_called()


def test_delete_note_scoped_to_orgnr():
    """Note belonging to a different orgnr must not be deleted."""
    db = _mock_db()
    # Simulate: the filter (id + orgnr combo) returns nothing
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(NotFoundError):
        BrokerService(db).delete_note(1, "000000000")


# ── @mention parsing (plan §🟢 #14) ──────────────────────────────────────────


def test_resolve_mentions_returns_only_same_firm_users():
    db = _mock_db()
    # Two candidates parsed from text; only one matches a same-firm user.
    db.query.return_value.filter.return_value.all.return_value = [
        (5, "alice@broker.no"),
    ]
    emails, ids = BrokerService(db)._resolve_mentions(
        "Hei @alice@broker.no — sjekk @random@external.com",
        firm_id=10,
    )
    assert emails == ["alice@broker.no"]
    assert ids == [5]


def test_resolve_mentions_no_candidates_returns_empty():
    db = _mock_db()
    emails, ids = BrokerService(db)._resolve_mentions("plain text", firm_id=10)
    assert emails == []
    assert ids == []
    db.query.assert_not_called()


def test_create_note_persists_mentions_and_fans_out_targeted_notifications():
    """End-to-end: create_note resolves mentions, persists them on the row,
    and the inbox service receives a targeted call (not the broad fan-out)."""
    from unittest.mock import patch

    db = _mock_db()
    # _resolve_mentions query: returns one matching user
    db.query.return_value.filter.return_value.all.return_value = [
        (5, "alice@broker.no"),
    ]
    body = SimpleNamespace(text="Hei @alice@broker.no, ta en titt")
    with patch(
        "api.services.notification_inbox_service.NotificationInboxService"
    ) as MockSvc:
        instance = MockSvc.return_value
        BrokerService(db).create_note(
            "123456789", body, firm_id=10, author_email="b@x.no",
        )
    # Targeted user_ids — must NOT be a broad fan-out.
    instance.create_for_users.assert_called_once()
    kwargs = instance.create_for_users.call_args.kwargs
    assert kwargs["user_ids"] == [5]
    assert kwargs["firm_id"] == 10


def test_create_note_skips_notifications_when_no_matching_users():
    """Mentions to non-firm emails should silently drop — no notifications fire."""
    from unittest.mock import patch

    db = _mock_db()
    db.query.return_value.filter.return_value.all.return_value = []  # no matches
    body = SimpleNamespace(text="@stranger@external.com please look")
    with patch(
        "api.services.notification_inbox_service.NotificationInboxService"
    ) as MockSvc:
        BrokerService(db).create_note(
            "123456789", body, firm_id=10, author_email="b@x.no",
        )
    MockSvc.assert_not_called()  # no fan-out at all


def test_create_note_works_without_firm_id_for_legacy_callers():
    """Backward-compat: omitting firm_id skips mention parsing entirely."""
    db = _mock_db()
    body = SimpleNamespace(text="@alice@broker.no")
    note = BrokerService(db).create_note("123456789", body)
    assert note.mentions is None  # mentions list never resolved
    db.query.assert_not_called()
