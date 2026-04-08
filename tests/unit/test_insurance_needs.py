"""Unit tests for api/services/insurance_needs.py.

Pure static tests — no DB, no network, no API keys.
"""
from api.services.insurance_needs import estimate_insurance_needs, _nace_section, _mnok, _estimate_premium


# ── _nace_section ─────────────────────────────────────────────────────────────

def test_nace_section_it():
    assert _nace_section("62") == "J"   # IT services


def test_nace_section_finance():
    assert _nace_section("64") == "K"   # Financial services


def test_nace_section_construction():
    assert _nace_section("41") == "F"


def test_nace_section_manufacturing():
    assert _nace_section("25") == "C"


def test_nace_section_wholesale():
    assert _nace_section("46") == "G"


def test_nace_section_unknown_returns_empty():
    assert _nace_section("999") == ""


def test_nace_section_none_returns_empty():
    assert _nace_section(None) == ""


def test_nace_section_decimal_code():
    assert _nace_section("62.01") == "J"


# ── _mnok ─────────────────────────────────────────────────────────────────────

def test_mnok_rounds_to_100k():
    assert _mnok(1_234_567) == 1_200_000


def test_mnok_exact():
    assert _mnok(5_000_000) == 5_000_000


# ── estimate_insurance_needs — Yrkesskadeforsikring ──────────────────────────

def test_yrkesskade_triggered_when_employees():
    needs = estimate_insurance_needs({"antall_ansatte": 10}, {})
    types = [n["type"] for n in needs]
    assert "Yrkesskadeforsikring" in types


def test_yrkesskade_not_triggered_no_employees():
    needs = estimate_insurance_needs({}, {})
    types = [n["type"] for n in needs]
    assert "Yrkesskadeforsikring" not in types


def test_yrkesskade_is_kritisk():
    needs = estimate_insurance_needs({"antall_ansatte": 5}, {})
    n = next(x for x in needs if x["type"] == "Yrkesskadeforsikring")
    assert n["priority"] == "Kritisk"


def test_yrkesskade_coverage_from_lonnskostnad():
    org = {"antall_ansatte": 10}
    regn = {"lonnskostnad": 4_000_000}
    needs = estimate_insurance_needs(org, regn)
    n = next(x for x in needs if x["type"] == "Yrkesskadeforsikring")
    assert n["estimated_coverage_nok"] == 60_000_000   # 4M × 15


def test_yrkesskade_coverage_fallback_headcount():
    needs = estimate_insurance_needs({"antall_ansatte": 2}, {})
    n = next(x for x in needs if x["type"] == "Yrkesskadeforsikring")
    assert n["estimated_coverage_nok"] == 18_000_000   # 2 × 600k × 15


def test_yrkesskade_coverage_minimum_5mnok():
    # 1 employee × 600k × 15 = 9 MNOK > 5 MNOK
    needs = estimate_insurance_needs({"antall_ansatte": 1}, {})
    n = next(x for x in needs if x["type"] == "Yrkesskadeforsikring")
    assert n["estimated_coverage_nok"] >= 5_000_000


# ── Ansvarsforsikring ─────────────────────────────────────────────────────────

def test_ansvarsforsikring_always_present():
    needs = estimate_insurance_needs({}, {})
    types = [n["type"] for n in needs]
    assert "Ansvarsforsikring" in types


def test_ansvarsforsikring_minimum_5mnok():
    needs = estimate_insurance_needs({}, {})
    n = next(x for x in needs if x["type"] == "Ansvarsforsikring")
    assert n["estimated_coverage_nok"] >= 5_000_000


def test_ansvarsforsikring_scales_with_revenue():
    needs = estimate_insurance_needs({}, {"sum_driftsinntekter": 200_000_000})
    n = next(x for x in needs if x["type"] == "Ansvarsforsikring")
    assert n["estimated_coverage_nok"] == 100_000_000   # 200M × 0.5


# ── Eiendomsforsikring ────────────────────────────────────────────────────────

def test_eiendom_triggered_above_5mnok_assets():
    needs = estimate_insurance_needs({}, {"sum_eiendeler": 10_000_000})
    types = [n["type"] for n in needs]
    assert "Eiendomsforsikring" in types


def test_eiendom_not_triggered_below_5mnok():
    needs = estimate_insurance_needs({}, {"sum_eiendeler": 4_000_000})
    types = [n["type"] for n in needs]
    assert "Eiendomsforsikring" not in types


def test_eiendom_coverage_80pct_of_assets():
    needs = estimate_insurance_needs({}, {"sum_eiendeler": 20_000_000})
    n = next(x for x in needs if x["type"] == "Eiendomsforsikring")
    assert n["estimated_coverage_nok"] == 16_000_000


# ── Styreansvarsforsikring ────────────────────────────────────────────────────

def test_dao_triggered_for_as():
    needs = estimate_insurance_needs({"organisasjonsform_kode": "AS"}, {})
    types = [n["type"] for n in needs]
    assert "Styreansvarsforsikring (D&O)" in types


def test_dao_triggered_for_asa():
    needs = estimate_insurance_needs({"organisasjonsform_kode": "ASA"}, {})
    types = [n["type"] for n in needs]
    assert "Styreansvarsforsikring (D&O)" in types


def test_dao_not_triggered_for_ank():
    needs = estimate_insurance_needs({"organisasjonsform_kode": "ANS"}, {})
    types = [n["type"] for n in needs]
    assert "Styreansvarsforsikring (D&O)" not in types


def test_dao_minimum_2mnok():
    needs = estimate_insurance_needs({"organisasjonsform_kode": "AS"}, {})
    n = next(x for x in needs if x["type"] == "Styreansvarsforsikring (D&O)")
    assert n["estimated_coverage_nok"] >= 2_000_000


# ── Cyberforsikring ───────────────────────────────────────────────────────────

def test_cyber_triggered_for_it_section():
    needs = estimate_insurance_needs({"naeringskode1": "62"}, {})  # J
    types = [n["type"] for n in needs]
    assert "Cyberforsikring" in types


def test_cyber_triggered_for_finance():
    needs = estimate_insurance_needs({"naeringskode1": "64"}, {})  # K
    types = [n["type"] for n in needs]
    assert "Cyberforsikring" in types


def test_cyber_not_triggered_for_construction():
    needs = estimate_insurance_needs({"naeringskode1": "41"}, {})  # F
    types = [n["type"] for n in needs]
    assert "Cyberforsikring" not in types


# ── Transportforsikring ───────────────────────────────────────────────────────

def test_transport_triggered_for_manufacturing():
    needs = estimate_insurance_needs({"naeringskode1": "25"}, {})  # C
    types = [n["type"] for n in needs]
    assert "Transportforsikring" in types


def test_transport_triggered_for_wholesale():
    needs = estimate_insurance_needs({"naeringskode1": "46"}, {})  # G
    types = [n["type"] for n in needs]
    assert "Transportforsikring" in types


# ── Nøkkelpersonforsikring ────────────────────────────────────────────────────

def test_nokkelperson_triggered_small_high_revenue():
    org = {"antall_ansatte": 10, "naeringskode1": "62"}
    regn = {"sum_driftsinntekter": 20_000_000}
    needs = estimate_insurance_needs(org, regn)
    types = [n["type"] for n in needs]
    assert "Nøkkelpersonforsikring" in types


def test_nokkelperson_not_triggered_large_company():
    org = {"antall_ansatte": 200}
    regn = {"sum_driftsinntekter": 200_000_000}
    needs = estimate_insurance_needs(org, regn)
    types = [n["type"] for n in needs]
    assert "Nøkkelpersonforsikring" not in types


def test_nokkelperson_not_triggered_low_revenue():
    needs = estimate_insurance_needs({"antall_ansatte": 5}, {"sum_driftsinntekter": 1_000_000})
    types = [n["type"] for n in needs]
    assert "Nøkkelpersonforsikring" not in types


# ── Kredittforsikring ─────────────────────────────────────────────────────────

def test_kreditt_triggered_for_wholesale():
    needs = estimate_insurance_needs({"naeringskode1": "46"}, {})  # G
    types = [n["type"] for n in needs]
    assert "Kredittforsikring" in types


def test_kreditt_triggered_large_revenue():
    needs = estimate_insurance_needs({}, {"sum_driftsinntekter": 100_000_000})
    types = [n["type"] for n in needs]
    assert "Kredittforsikring" in types


def test_kreditt_not_triggered_small_non_trade():
    needs = estimate_insurance_needs({"naeringskode1": "41"}, {"sum_driftsinntekter": 5_000_000})
    types = [n["type"] for n in needs]
    assert "Kredittforsikring" not in types


# ── Priority ordering ─────────────────────────────────────────────────────────

def test_kritisk_before_anbefalt_before_vurder():
    org = {
        "antall_ansatte": 10, "organisasjonsform_kode": "AS",
        "naeringskode1": "46",  # G — triggers transport + kreditt (Vurder)
    }
    regn = {"sum_driftsinntekter": 100_000_000, "sum_eiendeler": 20_000_000}
    needs = estimate_insurance_needs(org, regn)
    _order = {"Kritisk": 0, "Anbefalt": 1, "Vurder": 2}
    priorities = [_order[n["priority"]] for n in needs]
    assert priorities == sorted(priorities)


# ── Premium estimates ────────────────────────────────────────────────────────

def test_premium_has_low_mid_high():
    p = _estimate_premium("Ansvarsforsikring", 10_000_000, "J", 50, 100_000_000)
    assert "low" in p and "mid" in p and "high" in p


def test_premium_low_le_mid_le_high():
    p = _estimate_premium("Cyberforsikring", 20_000_000, "J", 30, 50_000_000)
    assert p["low"] <= p["mid"] <= p["high"]


def test_premium_high_risk_section_higher_than_low_risk():
    p_low = _estimate_premium("Ansvarsforsikring", 10_000_000, "M", 10, 10_000_000)
    p_high = _estimate_premium("Ansvarsforsikring", 10_000_000, "C", 10, 10_000_000)
    assert p_high["mid"] >= p_low["mid"]


def test_each_need_has_premium():
    needs = estimate_insurance_needs(
        {"antall_ansatte": 20, "organisasjonsform_kode": "AS", "naeringskode1": "62"},
        {"sum_driftsinntekter": 30_000_000, "sum_eiendeler": 8_000_000},
    )
    for n in needs:
        assert "estimated_annual_premium_nok" in n
        assert n["estimated_annual_premium_nok"]["mid"] > 0


# ── Full profile — DNB-like company ──────────────────────────────────────────

def test_full_financial_company():
    org = {
        "navn": "Test Finans AS",
        "organisasjonsform_kode": "AS",
        "naeringskode1": "64",  # K — finance
        "antall_ansatte": 500,
    }
    regn = {
        "sum_driftsinntekter": 5_000_000_000,
        "sum_eiendeler": 10_000_000_000,
        "lonnskostnad": 1_000_000_000,
    }
    needs = estimate_insurance_needs(org, regn)
    types = [n["type"] for n in needs]
    assert "Yrkesskadeforsikring" in types
    assert "Ansvarsforsikring" in types
    assert "Eiendomsforsikring" in types
    assert "Styreansvarsforsikring (D&O)" in types
    assert "Cyberforsikring" in types
    assert "Kredittforsikring" in types
    assert len(needs) >= 5
