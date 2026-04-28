"""Unit tests for api/main.py startup helpers and admin_router pure functions.

Tests _stamp_existing_db_if_needed, _run_migrations_with_lock, and
admin_router helpers (_has_mp4_faststart, _debug_db_status).
All DB and Alembic calls are mocked.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

sys.modules.setdefault("api.services.pdf_background", MagicMock())


def test_stamp_skipped_when_alembic_version_table_exists():
    from api.main import _stamp_existing_db_if_needed

    mock_conn = MagicMock()
    mock_conn.execute.return_value.scalar.return_value = True
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    cfg = MagicMock()
    with (
        patch("api.db.engine", mock_engine),
        patch("api.main.alembic_command") as mock_cmd,
    ):
        _stamp_existing_db_if_needed(cfg)
    mock_cmd.stamp.assert_not_called()


def test_stamp_called_when_no_version_table_but_companies_exist():
    from api.main import _stamp_existing_db_if_needed

    mock_conn = MagicMock()
    mock_conn.execute.return_value.scalar.side_effect = [False, True]
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    cfg = MagicMock()
    with (
        patch("api.db.engine", mock_engine),
        patch("api.main.alembic_command") as mock_cmd,
    ):
        _stamp_existing_db_if_needed(cfg)
    mock_cmd.stamp.assert_called_once_with(cfg, "4fa17f9b251a")


def test_stamp_skipped_when_no_version_table_and_no_companies():
    from api.main import _stamp_existing_db_if_needed

    mock_conn = MagicMock()
    mock_conn.execute.return_value.scalar.side_effect = [False, False]
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    cfg = MagicMock()
    with (
        patch("api.db.engine", mock_engine),
        patch("api.main.alembic_command") as mock_cmd,
    ):
        _stamp_existing_db_if_needed(cfg)
    mock_cmd.stamp.assert_not_called()


def test_migrations_run_with_lock_acquired():
    from api.main import _run_migrations_with_lock

    mock_conn = MagicMock()
    mock_conn.execute.return_value.scalar.return_value = True
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    cfg = MagicMock()
    with (
        patch("api.db.engine", mock_engine),
        patch("api.main.alembic_command") as mock_cmd,
    ):
        _run_migrations_with_lock(cfg)
    mock_cmd.upgrade.assert_called_once_with(cfg, "head")
    assert mock_conn.execute.call_count == 2


def test_migrations_skip_when_lock_held_throughout_wait():
    """Lock held by another worker for the full wait window — migration
    must be SKIPPED (not run unprotected). This is the core fix for the
    2026-04-28 outage; the previous behaviour ran upgrade unprotected,
    causing N workers to race for the table-level ACCESS EXCLUSIVE lock.
    """
    from api.main import _run_migrations_with_lock

    mock_conn = MagicMock()
    # Every try_advisory_lock returns False (lock perpetually held)
    mock_conn.execute.return_value.scalar.return_value = False
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    cfg = MagicMock()
    with (
        patch("api.db.engine", mock_engine),
        patch("api.main.alembic_command") as mock_cmd,
        patch("api.main.time.sleep"),  # skip the polling sleeps
    ):
        _run_migrations_with_lock(cfg)
    mock_cmd.upgrade.assert_not_called()


def test_migrations_run_after_lock_released_during_wait():
    """Lock initially held but released during the polling window — migration
    must run (no-op, since the holder finished it) and then release the lock."""
    from api.main import _run_migrations_with_lock

    mock_conn = MagicMock()
    # First try fails, second succeeds (holder released between polls)
    scalar_mock = MagicMock()
    scalar_mock.side_effect = [False, True]
    mock_conn.execute.return_value.scalar = scalar_mock
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    cfg = MagicMock()
    with (
        patch("api.db.engine", mock_engine),
        patch("api.main.alembic_command") as mock_cmd,
        patch("api.main.time.sleep"),
    ):
        _run_migrations_with_lock(cfg)
    mock_cmd.upgrade.assert_called_once_with(cfg, "head")


def test_migrations_release_lock_even_on_failure():
    from api.main import _run_migrations_with_lock

    mock_conn = MagicMock()
    mock_conn.execute.return_value.scalar.return_value = True
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    cfg = MagicMock()
    with (
        patch("api.db.engine", mock_engine),
        patch("api.main.alembic_command") as mock_cmd,
    ):
        mock_cmd.upgrade.side_effect = RuntimeError("migration failed")
        with pytest.raises(RuntimeError, match="migration failed"):
            _run_migrations_with_lock(cfg)
    assert mock_conn.execute.call_count == 2


def test_has_mp4_faststart_moov_before_mdat():
    from api.routers.debug import _has_mp4_faststart

    data = (16).to_bytes(4, "big") + b"moov" + b"\x00" * 8
    assert _has_mp4_faststart(data) is True


def test_has_mp4_faststart_mdat_before_moov():
    from api.routers.debug import _has_mp4_faststart

    data = (16).to_bytes(4, "big") + b"mdat" + b"\x00" * 8
    assert _has_mp4_faststart(data) is False


def test_has_mp4_faststart_inconclusive_on_short_data():
    from api.routers.debug import _has_mp4_faststart

    assert _has_mp4_faststart(b"\x00\x00") is None


def test_has_mp4_faststart_handles_ftyp_then_moov():
    from api.routers.debug import _has_mp4_faststart

    ftyp = (16).to_bytes(4, "big") + b"ftyp" + b"\x00" * 8
    moov = (16).to_bytes(4, "big") + b"moov" + b"\x00" * 8
    assert _has_mp4_faststart(ftyp + moov) is True


def test_debug_db_status_returns_version():
    from api.routers.debug import _debug_db_status

    mock_conn = MagicMock()
    mock_conn.execute.side_effect = [
        MagicMock(scalar=MagicMock(return_value="abc123")),
        MagicMock(fetchall=MagicMock(return_value=[("companies",), ("users",)])),
        MagicMock(scalar=MagicMock(return_value=True)),
    ]
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    with patch("api.db.engine", mock_engine):
        result = _debug_db_status()
    assert result["alembic_version"] == "abc123"
    assert "companies" in result["public_tables"]
    assert result["tags_column_exists"] is True


def test_debug_db_status_handles_exception():
    from api.routers.debug import _debug_db_status

    mock_engine = MagicMock()
    mock_engine.connect.side_effect = Exception("connection failed")

    with patch("api.db.engine", mock_engine):
        result = _debug_db_status()
    assert result["alembic_version"] is None
    assert "connection failed" in result["alembic_error"]


def test_build_coverage_gap_email_renders_html():
    from api.routers.cron import _build_coverage_gap_email

    gaps = [
        {
            "orgnr": "123",
            "navn": "TestCo",
            "gap_count": 2,
            "gaps": [{"type": "ansvar"}, {"type": "eiendom"}],
        },
    ]
    result = _build_coverage_gap_email(gaps)
    assert "TestCo" in result
    assert "ansvar" in result
    assert "<h2>" in result


def test_build_coverage_gap_email_multiple_companies():
    from api.routers.cron import _build_coverage_gap_email

    gaps = [
        {"orgnr": "1", "navn": "A", "gap_count": 1, "gaps": [{"type": "x"}]},
        {"orgnr": "2", "navn": "B", "gap_count": 1, "gaps": [{"type": "y"}]},
    ]
    result = _build_coverage_gap_email(gaps)
    assert "2 kunder" in result


def test_activity_to_dict_serializes():
    from api.routers.cron import _activity_to_dict
    from datetime import date

    a = MagicMock()
    a.orgnr = "999100101"
    a.subject = "Ring kunden"
    a.activity_type = MagicMock()
    a.activity_type.value = "call"
    a.due_date = date(2026, 5, 1)
    result = _activity_to_dict(a)
    assert result["orgnr"] == "999100101"
    assert result["subject"] == "Ring kunden"
    assert result["due_date"] == "2026-05-01"
