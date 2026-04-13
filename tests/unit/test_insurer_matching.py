"""Unit tests for api/services/insurer_matching.py — insurer scoring + ranking."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from api.services.insurer_matching import (
    _compute_win_rates,
    _resolve_product_types,
    _score_insurer,
    recommend_insurers,
)


def _insurer(id: int, name: str, appetite: list[str]) -> SimpleNamespace:
    return SimpleNamespace(id=id, name=name, appetite=appetite)


# ── _score_insurer ────────────────────────────────────────────────────────────

def test_score_full_appetite_match():
    ins = _insurer(1, "If", ["Eiendom", "Ansvar"])
    score = _score_insurer(ins, ["Eiendom", "Ansvar"], {1: 50.0})
    assert score == pytest.approx(0.6 * 1.0 + 0.4 * 0.5)


def test_score_partial_appetite_match():
    ins = _insurer(1, "If", ["Eiendom"])
    score = _score_insurer(ins, ["Eiendom", "Cyber"], {1: 0.0})
    assert score == pytest.approx(0.6 * 0.5 + 0.4 * 0.0)


def test_score_no_appetite_match():
    ins = _insurer(1, "If", ["Transport"])
    score = _score_insurer(ins, ["Cyber"], {})
    assert score == pytest.approx(0.0)


def test_score_empty_product_types():
    ins = _insurer(1, "If", ["Eiendom"])
    score = _score_insurer(ins, [], {1: 80.0})
    assert score == pytest.approx(0.6 * 0.0 + 0.4 * 0.8)


def test_score_empty_appetite():
    ins = _insurer(1, "If", [])
    score = _score_insurer(ins, ["Eiendom"], {})
    assert score == 0.0


def test_score_none_appetite():
    ins = SimpleNamespace(id=1, name="If", appetite=None)
    score = _score_insurer(ins, ["Eiendom"], {})
    assert score == 0.0


def test_score_case_insensitive():
    ins = _insurer(1, "If", ["eiendom"])
    score = _score_insurer(ins, ["Eiendom"], {})
    assert score > 0


def test_score_substring_match():
    """'cyber' in appetite matches 'Cyberforsikring' in product_types."""
    ins = _insurer(1, "If", ["cyber"])
    score = _score_insurer(ins, ["Cyberforsikring"], {})
    assert score > 0


# ── _compute_win_rates ────────────────────────────────────────────────────────

def test_compute_win_rates_basic():
    db = MagicMock()
    s1 = SimpleNamespace(insurer_id=1, status=SimpleNamespace(value="quoted"))
    s2 = SimpleNamespace(insurer_id=1, status=SimpleNamespace(value="declined"))
    s3 = SimpleNamespace(insurer_id=2, status=SimpleNamespace(value="quoted"))
    db.query.return_value.filter.return_value.all.return_value = [s1, s2, s3]
    rates = _compute_win_rates(1, db)
    assert rates[1] == pytest.approx(50.0)
    assert rates[2] == pytest.approx(100.0)


def test_compute_win_rates_empty():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []
    assert _compute_win_rates(1, db) == {}


# ── _resolve_product_types ────────────────────────────────────────────────────

def test_resolve_returns_explicit_types():
    db = MagicMock()
    result = _resolve_product_types("123", 1, ["Cyber"], db)
    assert result == ["Cyber"]


@patch("api.services.coverage_gap.analyze_coverage_gap")
def test_resolve_derives_from_gap_analysis(mock_gap):
    mock_gap.return_value = {
        "items": [
            {"type": "Cyber", "status": "gap"},
            {"type": "Eiendom", "status": "covered"},
        ]
    }
    db = MagicMock()
    result = _resolve_product_types("123", 1, None, db)
    assert result == ["Cyber"]


@patch("api.services.coverage_gap.analyze_coverage_gap", side_effect=Exception("fail"))
def test_resolve_returns_empty_on_gap_failure(mock_gap):
    db = MagicMock()
    result = _resolve_product_types("123", 1, None, db)
    assert result == []


# ── recommend_insurers ────────────────────────────────────────────────────────

@patch("api.services.insurer_matching._generate_reasoning", return_value="Good choice.")
def test_recommend_returns_top_n(mock_reason):
    db = MagicMock()
    company = SimpleNamespace(orgnr="123", navn="Test AS")
    db.query.return_value.filter.return_value.first.return_value = company
    db.query.return_value.filter.return_value.all.side_effect = [
        [_insurer(1, "If", ["Eiendom"]), _insurer(2, "Gjensidige", ["Cyber"])],
        [],  # submissions query
    ]
    result = recommend_insurers("123", 1, ["Eiendom"], db, top_n=1)
    assert len(result["recommendations"]) == 1
    assert result["company"]["orgnr"] == "123"


@patch("api.services.insurer_matching._generate_reasoning", return_value="OK")
def test_recommend_empty_when_no_insurers(mock_reason):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(orgnr="123", navn="X")
    db.query.return_value.filter.return_value.all.return_value = []
    result = recommend_insurers("123", 1, ["Eiendom"], db)
    assert result["recommendations"] == []
