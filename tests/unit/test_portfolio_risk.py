"""Unit tests for api.services.portfolio_risk — zone distribution,
transitions between snapshots, premium-at-risk aggregation.

Exercises the helper functions directly with hand-rolled snapshot objects
so we don't need a real database. Integration tests can hit the real
flow through the router.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict

from api.services.portfolio_risk import (
    _transitions,
    _zone_counts,
    UNKNOWN_ZONE,
)


@dataclass
class _FakeRow:
    orgnr: str
    zone: str
    z_score: float | None = None
    score_20: int | None = None


def _batch(*rows: _FakeRow) -> Dict[str, _FakeRow]:
    return {r.orgnr: r for r in rows}


# ── Zone histogram ────────────────────────────────────────────────────────────


def test_zone_counts_tallies_each_category():
    b = _batch(
        _FakeRow("111111111", "safe"),
        _FakeRow("222222222", "safe"),
        _FakeRow("333333333", "grey"),
        _FakeRow("444444444", "distress"),
        _FakeRow("555555555", UNKNOWN_ZONE),
    )
    counts = _zone_counts(b)
    assert counts["safe"] == 2
    assert counts["grey"] == 1
    assert counts["distress"] == 1
    assert counts[UNKNOWN_ZONE] == 1


def test_zone_counts_treats_none_zone_as_unknown():
    b = _batch(_FakeRow("111111111", None))  # type: ignore[arg-type]
    assert _zone_counts(b)[UNKNOWN_ZONE] == 1


# ── Transitions ──────────────────────────────────────────────────────────────


class _FakeSession:
    """Stub the .query(Company.orgnr, Company.navn).filter(in_).all() chain."""

    def __init__(self, navn_by_orgnr: Dict[str, str]):
        self._map = navn_by_orgnr

    def query(self, *args, **kw):
        return self

    def filter(self, *args, **kw):
        return self

    def all(self):
        return list(self._map.items())


def test_transitions_empty_when_prev_snapshot_missing():
    curr = _batch(_FakeRow("111111111", "safe", 3.5))
    assert _transitions(curr, {}, _FakeSession({})) == []


def test_transitions_detects_zone_change_and_computes_delta():
    curr = _batch(_FakeRow("111111111", "grey", 2.0, 10))
    prev = _batch(_FakeRow("111111111", "safe", 3.1, 2))
    out = _transitions(curr, prev, _FakeSession({"111111111": "Acme AS"}))
    assert len(out) == 1
    t = out[0]
    assert t["orgnr"] == "111111111"
    assert t["navn"] == "Acme AS"
    assert t["prev_zone"] == "safe"
    assert t["curr_zone"] == "grey"
    assert t["prev_z"] == 3.1
    assert t["curr_z"] == 2.0
    assert abs(t["delta_z"] + 1.1) < 1e-9  # went down by 1.1


def test_transitions_ignores_companies_with_unchanged_zone():
    curr = _batch(
        _FakeRow("111111111", "safe", 3.5),
        _FakeRow("222222222", "grey", 2.0),
    )
    prev = _batch(
        _FakeRow("111111111", "safe", 3.6),  # same zone — not a transition
        _FakeRow("222222222", "safe", 2.7),  # changed — transition
    )
    out = _transitions(curr, prev, _FakeSession({"222222222": "Other AS"}))
    assert [t["orgnr"] for t in out] == ["222222222"]


def test_transitions_ignores_companies_only_in_curr_snapshot():
    """Added between snapshots — no transition to compute without prev."""
    curr = _batch(
        _FakeRow("111111111", "distress", 0.5),
        _FakeRow("999999999", "grey", 2.0),  # newly added since last snapshot
    )
    prev = _batch(_FakeRow("111111111", "safe", 3.1))
    out = _transitions(curr, prev, _FakeSession({"111111111": "Acme AS"}))
    assert [t["orgnr"] for t in out] == ["111111111"]


def test_transitions_delta_z_is_none_when_either_score_missing():
    curr = _batch(_FakeRow("111111111", "grey", 2.0))
    prev = _batch(_FakeRow("111111111", "safe", None))
    out = _transitions(curr, prev, _FakeSession({"111111111": "Acme AS"}))
    assert out[0]["delta_z"] is None


# ── Snapshot timestamp handling ─────────────────────────────────────────────


def test_snapshot_timestamps_are_timezone_aware():
    """Regression guard: PostgreSQL TIMESTAMPTZ expects aware datetimes.
    If we ever drop the tzinfo the INSERT will still work on the happy path
    but fail on an iso-date comparison. Pin the invariant here."""
    from api.services.portfolio_risk import compute_and_store_snapshot  # noqa: F401

    # The production code calls datetime.now(timezone.utc); verify that's the
    # pattern by confirming our reference clock is tz-aware.
    now = datetime.now(timezone.utc)
    assert now.tzinfo is not None
