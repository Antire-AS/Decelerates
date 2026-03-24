"""Tests for api/risk.py — build_risk_summary and derive_simple_risk edge cases.

These complement the 54 tests in test_risk.py (which cover derive_simple_risk).
Pure logic — no DB, no network.
"""
import pytest
from api.risk import build_risk_summary, derive_simple_risk


# ── Helpers ───────────────────────────────────────────────────────────────────

def _org(**kwargs):
    base = {
        "orgnr": "123456789",
        "navn": "Test AS",
        "organisasjonsform": "Aksjeselskap",
        "organisasjonsform_kode": "AS",
        "kommune": "Oslo",
        "land": "NOR",
        "naeringskode1": "62.010",
        "naeringskode1_beskrivelse": "Utvikling av programvare",
        "stiftelsesdato": "2010-01-01",
    }
    base.update(kwargs)
    return base


def _regn(**kwargs):
    base = {
        "regnskapsår": 2024,
        "sum_driftsinntekter": 50_000_000,
        "sum_egenkapital": 20_000_000,
        "sum_eiendeler": 80_000_000,
        "aarsresultat": 5_000_000,
        "antall_ansatte": 50,
        "sum_gjeld": 60_000_000,
    }
    base.update(kwargs)
    return base


def _risk(**kwargs):
    base = {
        "score": 2,
        "reasons": ["Aksjeselskap (AS/ASA)"],
        "factors": [{"label": "Aksjeselskap (AS/ASA)", "points": 1,
                     "category": "Selskapsstatus", "detail": ""}],
        "equity_ratio": 0.25,
    }
    base.update(kwargs)
    return base


def _pep(**kwargs):
    base = {"hit_count": 0}
    base.update(kwargs)
    return base


# ── build_risk_summary — field mapping ────────────────────────────────────────

def test_build_risk_summary_includes_orgnr():
    result = build_risk_summary(_org(), _regn(), _risk(), _pep())
    assert result["orgnr"] == "123456789"


def test_build_risk_summary_includes_navn():
    result = build_risk_summary(_org(navn="DNB Bank ASA"), _regn(), _risk(), _pep())
    assert result["navn"] == "DNB Bank ASA"


def test_build_risk_summary_includes_risk_score():
    result = build_risk_summary(_org(), _regn(), _risk(score=5), _pep())
    assert result["risk_score"] == 5


def test_build_risk_summary_includes_risk_flags():
    flags = ["Negativ egenkapital", "Nystartet selskap (<2 år)"]
    result = build_risk_summary(_org(), _regn(), _risk(reasons=flags), _pep())
    assert result["risk_flags"] == flags


def test_build_risk_summary_includes_pep_hits():
    result = build_risk_summary(_org(), _regn(), _risk(), _pep(hit_count=3))
    assert result["pep_hits"] == 3


def test_build_risk_summary_pep_zero_when_no_hits():
    result = build_risk_summary(_org(), _regn(), _risk(), _pep(hit_count=0))
    assert result["pep_hits"] == 0


def test_build_risk_summary_equity_ratio_from_risk():
    result = build_risk_summary(_org(), _regn(), _risk(equity_ratio=0.42), _pep())
    assert result["egenkapitalandel"] == pytest.approx(0.42)


def test_build_risk_summary_includes_financial_fields():
    result = build_risk_summary(
        _org(), _regn(sum_driftsinntekter=100_000_000, aarsresultat=-5_000_000),
        _risk(), _pep()
    )
    assert result["omsetning"] == 100_000_000
    assert result["aarsresultat"] == -5_000_000


def test_build_risk_summary_includes_ansatte():
    result = build_risk_summary(_org(), _regn(antall_ansatte=250), _risk(), _pep())
    assert result["antall_ansatte"] == 250


def test_build_risk_summary_konkurs_false_by_default():
    result = build_risk_summary(_org(), _regn(), _risk(), _pep())
    assert result["konkurs"] is False
    assert result["under_konkursbehandling"] is False
    assert result["under_avvikling"] is False


def test_build_risk_summary_konkurs_true_when_set():
    result = build_risk_summary(
        _org(konkurs=True, under_konkursbehandling=True), _regn(), _risk(), _pep()
    )
    assert result["konkurs"] is True
    assert result["under_konkursbehandling"] is True


def test_build_risk_summary_municipality():
    result = build_risk_summary(_org(kommune="Bergen"), _regn(), _risk(), _pep())
    assert result["kommune"] == "Bergen"


# ── build_risk_summary — None / empty inputs ──────────────────────────────────

def test_build_risk_summary_none_risk_returns_none_score():
    result = build_risk_summary(_org(), _regn(), None, _pep())
    assert result["risk_score"] is None
    assert result["risk_flags"] == []


def test_build_risk_summary_none_pep_returns_zero_hits():
    result = build_risk_summary(_org(), _regn(), _risk(), None)
    assert result["pep_hits"] == 0


def test_build_risk_summary_empty_regn():
    result = build_risk_summary(_org(), {}, _risk(), _pep())
    assert result["omsetning"] is None
    assert result["aarsresultat"] is None


def test_build_risk_summary_empty_risk_dict():
    result = build_risk_summary(_org(), _regn(), {}, _pep())
    assert result["risk_score"] is None
    assert result["risk_flags"] == []


# ── derive_simple_risk — edge cases not covered in test_risk.py ───────────────

def test_derive_simple_risk_zero_score_for_clean_company():
    """A healthy Norwegian AS with good financials should have a low score."""
    org = {
        "organisasjonsform_kode": "NUF",  # not AS — no AS points
        "land": "NOR",
        "naeringskode1": "62.010",        # IT — moderate sector
    }
    regn = {
        "sum_driftsinntekter": 5_000_000,  # below 10M — no size risk
        "sum_egenkapital": 2_000_000,
        "sum_eiendeler": 8_000_000,        # 25% equity ratio
        "aarsresultat": 500_000,           # positive
    }
    result = derive_simple_risk(org, regn)
    # Only sector risk expected (IT is MED_RISK_NACE → 1 point)
    assert result["score"] >= 0
    assert "reasons" in result
    assert "factors" in result


def test_derive_simple_risk_returns_required_keys():
    result = derive_simple_risk({}, {})
    assert "score" in result
    assert "factors" in result
    assert "reasons" in result
    assert "equity_ratio" in result


def test_derive_simple_risk_equity_ratio_none_for_zero_assets():
    regn = {"sum_egenkapital": 1_000_000, "sum_eiendeler": 0}
    result = derive_simple_risk({}, regn)
    assert result["equity_ratio"] is None


def test_derive_simple_risk_reasons_match_factors():
    result = derive_simple_risk(_org(), _regn())
    labels_from_factors = [f["label"] for f in result["factors"]]
    assert result["reasons"] == labels_from_factors


def test_derive_simple_risk_factors_have_required_keys():
    result = derive_simple_risk(_org(), _regn())
    for factor in result["factors"]:
        assert "label" in factor
        assert "points" in factor
        assert "category" in factor


def test_derive_simple_risk_bankruptcy_flag_adds_5_points():
    org = _org(konkurs=True, under_konkursbehandling=True)
    result = derive_simple_risk(org, _regn())
    labels = result["reasons"]
    assert any("Konkursbehandling" in l for l in labels)
    points_for_konkurs = sum(
        f["points"] for f in result["factors"] if "Konkursbehandling" in f["label"]
    )
    assert points_for_konkurs == 5


def test_derive_simple_risk_avvikling_adds_3_points():
    org = _org(under_avvikling=True)
    result = derive_simple_risk(org, _regn())
    points = sum(f["points"] for f in result["factors"] if "avvikling" in f["label"].lower())
    assert points == 3


def test_derive_simple_risk_very_negative_equity_adds_4_points():
    regn = _regn(sum_egenkapital=-50_000_000, sum_eiendeler=100_000_000)
    result = derive_simple_risk({}, regn)
    equity_factors = [f for f in result["factors"] if "egenkapital" in f["label"].lower()]
    total_equity_points = sum(f["points"] for f in equity_factors)
    assert total_equity_points >= 4


def test_derive_simple_risk_high_employee_count():
    regn = _regn(antall_ansatte=1500)
    result = derive_simple_risk({}, regn)
    labels = result["reasons"]
    assert any("1000 ansatte" in l for l in labels)


def test_derive_simple_risk_pep_hit_adds_2_points():
    result_no_pep  = derive_simple_risk(_org(), _regn(), pep=None)
    result_pep_hit = derive_simple_risk(_org(), _regn(), pep={"hit_count": 1})
    assert result_pep_hit["score"] == result_no_pep["score"] + 2
