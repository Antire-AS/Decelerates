"""Unit tests for the nightly Altman-snapshot monitor.

The monitor's two job dispatches: (a) take a snapshot per portfolio and
(b) detect zone transitions across snapshots. We exercise the pure
transition logic (worsening-only filter) and the user-fan-out logic
directly with mocked DB sessions — the integration test covers the
full orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from api.services.altman_snapshot_monitor import (
    _WORSENING_TRANSITIONS,
    _fire_zone_change_notifications,
    _transitions_of_concern,
    _users_in_firm,
)


# ── Worsening-filter constants ──────────────────────────────────────────────


def test_worsening_set_covers_every_downgrade_path():
    """Spec: only safe→grey, safe→distress, grey→distress trigger
    notifications. Recovery (grey→safe, distress→grey, distress→safe)
    is good news and doesn't need to push."""
    assert ("safe", "grey") in _WORSENING_TRANSITIONS
    assert ("safe", "distress") in _WORSENING_TRANSITIONS
    assert ("grey", "distress") in _WORSENING_TRANSITIONS
    assert ("grey", "safe") not in _WORSENING_TRANSITIONS
    assert ("distress", "grey") not in _WORSENING_TRANSITIONS
    assert ("distress", "safe") not in _WORSENING_TRANSITIONS


# ── Transition detection ────────────────────────────────────────────────────


@dataclass
class _Snapshot:
    orgnr: str
    zone: str
    z_score: float = 0.0
    score_20: int = 0


def test_transitions_empty_when_no_previous_snapshot():
    db = MagicMock()
    with patch(
        "api.services.altman_snapshot_monitor._latest_two_batch_timestamps",
        return_value=(object(), None),
    ):
        assert _transitions_of_concern(1, db) == []


def test_transitions_filters_out_recovery():
    """Company moving grey→safe is recovery, not a concern."""
    curr_ts, prev_ts = object(), object()
    curr_batch = {"111111111": _Snapshot("111111111", "safe")}
    prev_batch = {"111111111": _Snapshot("111111111", "grey")}
    db = MagicMock()
    db.query().filter().all.return_value = [("111111111", "Recovering AS")]
    with (
        patch(
            "api.services.altman_snapshot_monitor._latest_two_batch_timestamps",
            return_value=(curr_ts, prev_ts),
        ),
        patch(
            "api.services.altman_snapshot_monitor._load_batch",
            side_effect=[curr_batch, prev_batch],
        ),
    ):
        assert _transitions_of_concern(1, db) == []


def test_transitions_detects_safe_to_distress():
    curr_ts, prev_ts = object(), object()
    curr = {"111111111": _Snapshot("111111111", "distress", -0.5, 20)}
    prev = {"111111111": _Snapshot("111111111", "safe", 3.8, 0)}
    db = MagicMock()
    db.query().filter().all.return_value = [("111111111", "Falling AS")]
    with (
        patch(
            "api.services.altman_snapshot_monitor._latest_two_batch_timestamps",
            return_value=(curr_ts, prev_ts),
        ),
        patch(
            "api.services.altman_snapshot_monitor._load_batch",
            side_effect=[curr, prev],
        ),
    ):
        out = _transitions_of_concern(1, db)
    assert len(out) == 1
    assert out[0]["orgnr"] == "111111111"
    assert out[0]["navn"] == "Falling AS"
    assert out[0]["prev_zone"] == "safe"
    assert out[0]["curr_zone"] == "distress"


def test_transitions_ignores_unchanged_zones():
    curr_ts, prev_ts = object(), object()
    curr = {"111111111": _Snapshot("111111111", "grey", 2.0, 10)}
    prev = {"111111111": _Snapshot("111111111", "grey", 2.2, 9)}
    db = MagicMock()
    with (
        patch(
            "api.services.altman_snapshot_monitor._latest_two_batch_timestamps",
            return_value=(curr_ts, prev_ts),
        ),
        patch(
            "api.services.altman_snapshot_monitor._load_batch",
            side_effect=[curr, prev],
        ),
    ):
        assert _transitions_of_concern(1, db) == []


# ── Notification fan-out ────────────────────────────────────────────────────


class _StubPortfolio:
    def __init__(self, id: int, name: str, firm_id: int | None):
        self.id = id
        self.name = name
        self.firm_id = firm_id


def test_fire_zone_change_writes_one_notification_per_user_per_transition():
    db = MagicMock()
    with (
        patch(
            "api.services.altman_snapshot_monitor._users_in_firm",
            return_value=[101, 102, 103],
        ),
        patch(
            "api.services.altman_snapshot_monitor.create_notification_for_users_safe"
        ) as mock_fn,
    ):
        portfolio = _StubPortfolio(id=5, name="Firma A", firm_id=42)
        transitions = [
            {
                "orgnr": "111111111",
                "navn": "Acme AS",
                "prev_zone": "safe",
                "curr_zone": "grey",
            },
            {
                "orgnr": "222222222",
                "navn": "Other AS",
                "prev_zone": "grey",
                "curr_zone": "distress",
            },
        ]
        written = _fire_zone_change_notifications(portfolio, transitions, db)
    # 2 transitions × 3 users = 6 notifications written
    assert written == 6
    # One call per transition — the mocked sender takes a list of user_ids
    assert mock_fn.call_count == 2


def test_fire_zone_change_returns_zero_when_no_users_in_firm():
    db = MagicMock()
    with (
        patch(
            "api.services.altman_snapshot_monitor._users_in_firm",
            return_value=[],
        ),
        patch(
            "api.services.altman_snapshot_monitor.create_notification_for_users_safe"
        ) as mock_fn,
    ):
        portfolio = _StubPortfolio(id=5, name="Empty firm", firm_id=999)
        transitions = [
            {
                "orgnr": "111111111",
                "navn": "Acme AS",
                "prev_zone": "safe",
                "curr_zone": "distress",
            }
        ]
        written = _fire_zone_change_notifications(portfolio, transitions, db)
    assert written == 0
    mock_fn.assert_not_called()


def test_fire_zone_change_empty_transitions_is_noop():
    db = MagicMock()
    portfolio = _StubPortfolio(id=5, name="X", firm_id=1)
    assert _fire_zone_change_notifications(portfolio, [], db) == 0


# ── User-lookup filtering ───────────────────────────────────────────────────


def test_users_in_firm_system_wide_portfolio_skipped():
    """firm_id=None → no well-defined audience → empty list, no DB query."""
    db = MagicMock()
    assert _users_in_firm(None, db) == []
    db.query.assert_not_called()


def test_users_in_firm_scopes_to_firm_id_when_given():
    db = MagicMock()
    fake_q = MagicMock()
    fake_q.filter.return_value = fake_q
    fake_q.all.return_value = [(10,), (20,), (30,)]
    db.query.return_value = fake_q
    assert _users_in_firm(42, db) == [10, 20, 30]
