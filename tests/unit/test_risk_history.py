"""Unit tests for api.services.risk_history.get_altman_z_history.

These tests exercise the service against hand-rolled CompanyHistory rows,
not a real database — the SQLAlchemy session is replaced with a fake whose
query().filter().order_by().all() chain returns the synthetic rows. This
keeps the test fast and pins the contract on what matters: which rows turn
into points and which get silently skipped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from api.services.risk_history import get_altman_z_history


@dataclass
class _FakeRow:
    year: int
    raw: Dict[str, Any] = field(default_factory=dict)


class _FakeQuery:
    def __init__(self, rows: List[_FakeRow]):
        self._rows = rows

    def filter(self, *_args, **_kw) -> "_FakeQuery":
        return self

    def order_by(self, *_args, **_kw) -> "_FakeQuery":
        return self

    def all(self) -> List[_FakeRow]:
        return self._rows


class _FakeSession:
    def __init__(self, rows: List[_FakeRow]):
        self._rows = rows

    def query(self, *_args, **_kw) -> _FakeQuery:
        return _FakeQuery(self._rows)


def _complete_regn(total_assets: float, ebit: float) -> Dict[str, Any]:
    """A regn blob that has every field compute_altman_z_score needs."""
    return {
        "sum_eiendeler": total_assets,
        "sum_gjeld": total_assets * 0.4,
        "sum_egenkapital": total_assets * 0.6,
        "driftsresultat": ebit,
        "sum_opptjent_egenkapital": total_assets * 0.3,
        "sum_omloepsmidler": total_assets * 0.5,
        "short_term_debt": total_assets * 0.1,
    }


def test_returns_one_point_per_row_when_all_financials_complete():
    db = _FakeSession(
        [
            _FakeRow(year=2022, raw=_complete_regn(1_000_000, 150_000)),
            _FakeRow(year=2023, raw=_complete_regn(1_100_000, 180_000)),
            _FakeRow(year=2024, raw=_complete_regn(1_250_000, 210_000)),
        ]
    )
    points = get_altman_z_history(db, "123456789")
    assert [p["year"] for p in points] == [2022, 2023, 2024]
    for p in points:
        assert isinstance(p["z_score"], float)
        assert p["zone"] in {"safe", "grey", "distress"}
        assert 0 <= p["score_20"] <= 20


def test_skips_rows_with_missing_altman_inputs():
    partial = {"sum_eiendeler": 1_000_000, "sum_egenkapital": 400_000}
    db = _FakeSession(
        [
            _FakeRow(year=2021, raw=partial),
            _FakeRow(year=2022, raw=_complete_regn(1_000_000, 120_000)),
            _FakeRow(year=2023, raw={}),
            _FakeRow(year=2024, raw=_complete_regn(1_200_000, 180_000)),
        ]
    )
    points = get_altman_z_history(db, "123456789")
    assert [p["year"] for p in points] == [2022, 2024]


def test_returns_empty_when_no_rows():
    db = _FakeSession([])
    assert get_altman_z_history(db, "999999999") == []


def test_tolerates_none_raw_column():
    db = _FakeSession(
        [
            _FakeRow(year=2023, raw=None),  # type: ignore[arg-type]
            _FakeRow(year=2024, raw=_complete_regn(2_000_000, 300_000)),
        ]
    )
    points = get_altman_z_history(db, "123456789")
    assert [p["year"] for p in points] == [2024]
