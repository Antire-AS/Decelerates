"""Tests for risk.py — derive_simple_risk and build_risk_summary."""

import pytest
from api.risk import derive_simple_risk, build_risk_summary


# ── Helpers ──────────────────────────────────────────────────────────────────


def _org(**kwargs):
    base = {
        "orgnr": "123456789",
        "navn": "Test AS",
        "organisasjonsform_kode": "AS",
        "naeringskode1": None,
        "naeringskode1_beskrivelse": "",
        "stiftelsesdato": None,
        "konkurs": False,
        "under_konkursbehandling": False,
        "under_avvikling": False,
    }
    base.update(kwargs)
    return base


def _regn(**kwargs):
    base = {
        "sum_driftsinntekter": 0,
        "sum_egenkapital": 0,
        "sum_eiendeler": 0,
        "aarsresultat": None,
        "sum_gjeld": None,
        "antall_ansatte": None,
    }
    base.update(kwargs)
    return base


def _labels(result):
    return [f["label"] for f in result["factors"]]


# ── Return structure ──────────────────────────────────────────────────────────


def test_returns_required_keys():
    result = derive_simple_risk(_org(), _regn())
    assert "score" in result
    assert "factors" in result
    assert "reasons" in result
    assert "equity_ratio" in result


def test_reasons_matches_factor_labels():
    result = derive_simple_risk(
        _org(naeringskode1="41.20"), _regn(sum_driftsinntekter=200_000_000)
    )
    assert result["reasons"] == _labels(result)


def test_score_equals_sum_of_factor_points():
    result = derive_simple_risk(
        _org(naeringskode1="41.20"),
        _regn(
            sum_driftsinntekter=200_000_000,
            sum_egenkapital=-500_000,
            sum_eiendeler=5_000_000,
        ),
    )
    assert result["score"] == sum(f["points"] for f in result["factors"])


def test_empty_inputs_zero_score():
    result = derive_simple_risk(_org(organisasjonsform_kode="ENK"), _regn())
    assert result["score"] == 0
    assert result["factors"] == []
    assert result["reasons"] == []
    assert result["equity_ratio"] is None


# ── Selskapsstatus ────────────────────────────────────────────────────────────


def test_konkurs_adds_5():
    result = derive_simple_risk(_org(konkurs=True), _regn())
    assert result["score"] >= 5
    assert any("Konkurs" in f["label"] for f in result["factors"])
    assert any(f["category"] == "Selskapsstatus" for f in result["factors"])


def test_under_konkursbehandling_adds_5():
    result = derive_simple_risk(_org(under_konkursbehandling=True), _regn())
    assert result["score"] >= 5


def test_avvikling_adds_3():
    result = derive_simple_risk(_org(under_avvikling=True), _regn())
    assert result["score"] >= 3
    assert any("avvikling" in f["label"].lower() for f in result["factors"])


def test_as_adds_1():
    result = derive_simple_risk(_org(organisasjonsform_kode="AS"), _regn())
    assert any("AS" in f["label"] for f in result["factors"])


def test_asa_adds_1():
    result = derive_simple_risk(_org(organisasjonsform_kode="ASA"), _regn())
    assert any("AS" in f["label"] for f in result["factors"])


def test_enk_no_form_score():
    result = derive_simple_risk(_org(organisasjonsform_kode="ENK"), _regn())
    assert not any("AS" in f["label"] for f in result["factors"])


# ── Økonomi — omsetning ───────────────────────────────────────────────────────


def test_high_turnover_100m_adds_1():
    result = derive_simple_risk(_org(), _regn(sum_driftsinntekter=200_000_000))
    assert any(
        f["points"] == 1 and "omsetning" in f["label"].lower()
        for f in result["factors"]
    )


def test_mid_turnover_10m_adds_1():
    result = derive_simple_risk(_org(), _regn(sum_driftsinntekter=50_000_000))
    assert any(
        f["points"] == 1 and "omsetning" in f["label"].lower()
        for f in result["factors"]
    )


def test_low_turnover_no_score():
    result = derive_simple_risk(_org(), _regn(sum_driftsinntekter=5_000_000))
    assert not any("omsetning" in f["label"].lower() for f in result["factors"])


# ── Økonomi — egenkapital ────────────────────────────────────────────────────


def test_negative_equity_adds_2():
    result = derive_simple_risk(
        _org(), _regn(sum_egenkapital=-1_000_000, sum_eiendeler=10_000_000)
    )
    assert any("Negativ egenkapital" in f["label"] for f in result["factors"])
    assert result["equity_ratio"] < 0


def test_low_equity_ratio_adds_1():
    # 10% < 20% threshold
    result = derive_simple_risk(
        _org(), _regn(sum_egenkapital=1_000_000, sum_eiendeler=10_000_000)
    )
    assert any("Lav egenkapitalandel" in f["label"] for f in result["factors"])
    assert abs(result["equity_ratio"] - 0.1) < 0.001


def test_healthy_equity_no_score():
    # 40% > 20% threshold
    result = derive_simple_risk(
        _org(), _regn(sum_egenkapital=4_000_000, sum_eiendeler=10_000_000)
    )
    assert not any("egenkapital" in f["label"].lower() for f in result["factors"])


def test_equity_ratio_calculated_correctly():
    result = derive_simple_risk(
        _org(), _regn(sum_egenkapital=3_000_000, sum_eiendeler=10_000_000)
    )
    assert abs(result["equity_ratio"] - 0.3) < 0.001


def test_equity_ratio_none_when_no_assets():
    result = derive_simple_risk(_org(), _regn(sum_eiendeler=0))
    assert result["equity_ratio"] is None


# ── Økonomi — årsresultat ─────────────────────────────────────────────────────


def test_negative_aarsresultat_adds_1():
    result = derive_simple_risk(_org(), _regn(aarsresultat=-500_000))
    assert any("årsresultat" in f["label"].lower() for f in result["factors"])
    assert any(
        f["category"] == "Økonomi" and "årsresultat" in f["label"].lower()
        for f in result["factors"]
    )


def test_positive_aarsresultat_no_score():
    result = derive_simple_risk(_org(), _regn(aarsresultat=500_000))
    assert not any("årsresultat" in f["label"].lower() for f in result["factors"])


def test_zero_aarsresultat_no_score():
    result = derive_simple_risk(_org(), _regn(aarsresultat=0))
    assert not any("årsresultat" in f["label"].lower() for f in result["factors"])


# ── Økonomi — gjeldsgrad ─────────────────────────────────────────────────────


def test_very_high_debt_over_80pct_adds_2():
    result = derive_simple_risk(
        _org(), _regn(sum_gjeld=9_000_000, sum_eiendeler=10_000_000)
    )
    assert any(
        f["points"] == 2 and "gjeldsgrad" in f["label"].lower()
        for f in result["factors"]
    )


def test_high_debt_60_to_80pct_adds_1():
    result = derive_simple_risk(
        _org(), _regn(sum_gjeld=7_000_000, sum_eiendeler=10_000_000)
    )
    assert any(
        f["points"] == 1 and "gjeldsgrad" in f["label"].lower()
        for f in result["factors"]
    )


def test_low_debt_no_score():
    result = derive_simple_risk(
        _org(), _regn(sum_gjeld=3_000_000, sum_eiendeler=10_000_000)
    )
    assert not any("gjeldsgrad" in f["label"].lower() for f in result["factors"])


def test_no_gjeld_field_no_score():
    result = derive_simple_risk(_org(), _regn(sum_gjeld=None, sum_eiendeler=10_000_000))
    assert not any("gjeldsgrad" in f["label"].lower() for f in result["factors"])


# ── Bransjerisiko ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "nace", ["41.20", "42.10", "43.21", "49.10", "52.10", "64.11", "77.10"]
)
def test_high_risk_nace_sections_add_2(nace):
    result = derive_simple_risk(_org(naeringskode1=nace), _regn())
    assert any(
        f["points"] == 2 and f["category"] == "Bransje" for f in result["factors"]
    ), f"Expected +2 for NACE {nace}"


@pytest.mark.parametrize("nace", ["10.11", "46.10", "55.10", "62.01"])
def test_med_risk_nace_sections_add_1(nace):
    result = derive_simple_risk(_org(naeringskode1=nace), _regn())
    assert any(
        f["points"] == 1 and f["category"] == "Bransje" for f in result["factors"]
    ), f"Expected +1 for NACE {nace}"


@pytest.mark.parametrize("nace", ["85.10", "84.11", "01.11"])
def test_low_risk_nace_no_bransje_score(nace):
    result = derive_simple_risk(_org(naeringskode1=nace), _regn())
    assert not any(f["category"] == "Bransje" for f in result["factors"]), (
        f"Expected no Bransje score for NACE {nace}"
    )


def test_no_nace_no_bransje_score():
    result = derive_simple_risk(_org(naeringskode1=None), _regn())
    assert not any(f["category"] == "Bransje" for f in result["factors"])


# ── Selskapets alder ──────────────────────────────────────────────────────────


def test_company_under_2_years_adds_3():
    result = derive_simple_risk(_org(stiftelsesdato="2024-06-01"), _regn())
    assert any(
        f["points"] == 3 and "Nystartet" in f["label"] for f in result["factors"]
    )


def test_company_2_to_5_years_adds_1():
    result = derive_simple_risk(_org(stiftelsesdato="2022-01-01"), _regn())
    assert any(
        f["points"] == 1 and f["category"] == "Historikk" for f in result["factors"]
    )


def test_established_company_no_age_score():
    result = derive_simple_risk(_org(stiftelsesdato="2010-01-01"), _regn())
    assert not any(f["category"] == "Historikk" for f in result["factors"])


def test_no_stiftelsesdato_no_age_score():
    result = derive_simple_risk(_org(stiftelsesdato=None), _regn())
    assert not any(f["category"] == "Historikk" for f in result["factors"])


# ── Antall ansatte ────────────────────────────────────────────────────────────


def test_over_200_employees_adds_1():
    result = derive_simple_risk(_org(), _regn(antall_ansatte=500))
    assert any("ansatte" in f["label"].lower() for f in result["factors"])


def test_exactly_200_employees_no_score():
    result = derive_simple_risk(_org(), _regn(antall_ansatte=200))
    assert not any("ansatte" in f["label"].lower() for f in result["factors"])


def test_few_employees_no_score():
    result = derive_simple_risk(_org(), _regn(antall_ansatte=50))
    assert not any("ansatte" in f["label"].lower() for f in result["factors"])


# ── PEP/sanksjoner ────────────────────────────────────────────────────────────


def test_pep_hit_adds_2():
    result = derive_simple_risk(_org(), _regn(), pep={"hit_count": 3})
    assert any(f["points"] == 2 and "PEP" in f["label"] for f in result["factors"])


def test_pep_zero_no_score():
    result = derive_simple_risk(_org(), _regn(), pep={"hit_count": 0})
    assert not any("PEP" in f["label"] for f in result["factors"])


def test_pep_none_no_score():
    result = derive_simple_risk(_org(), _regn(), pep=None)
    assert not any("PEP" in f["label"] for f in result["factors"])


# ── Accumulation ─────────────────────────────────────────────────────────────


def test_worst_case_accumulates_all_factors():
    """A bankrupt new company in high-risk industry with bad financials."""
    result = derive_simple_risk(
        _org(
            organisasjonsform_kode="AS",
            konkurs=True,
            naeringskode1="41.20",
            stiftelsesdato="2025-01-01",
        ),
        _regn(
            sum_driftsinntekter=200_000_000,
            sum_egenkapital=-1_000_000,
            sum_eiendeler=10_000_000,
            aarsresultat=-500_000,
            sum_gjeld=9_500_000,
            antall_ansatte=300,
        ),
        pep={"hit_count": 2},
    )
    assert result["score"] >= 15
    assert len(result["factors"]) >= 6


# ── build_risk_summary ────────────────────────────────────────────────────────


def test_build_risk_summary_maps_fields():
    org = _org(navn="Stor AS", orgnr="987654321", kommune="BERGEN", land="Norge")
    regn = _regn(
        sum_driftsinntekter=50_000_000, aarsresultat=1_000_000, antall_ansatte=80
    )
    risk = {
        "score": 5,
        "reasons": ["Høy omsetning"],
        "factors": [],
        "equity_ratio": 0.25,
    }
    pep = {"hit_count": 0}

    summary = build_risk_summary(org, regn, risk, pep)

    assert summary["navn"] == "Stor AS"
    assert summary["orgnr"] == "987654321"
    assert summary["risk_score"] == 5
    assert summary["pep_hits"] == 0
    assert summary["omsetning"] == 50_000_000
    assert summary["antall_ansatte"] == 80
    assert summary["egenkapitalandel"] == 0.25
    assert summary["konkurs"] is False


def test_build_risk_summary_bankruptcy_flags():
    org = _org(konkurs=True, under_konkursbehandling=True, under_avvikling=False)
    summary = build_risk_summary(org, _regn(), {}, {})
    assert summary["konkurs"] is True
    assert summary["under_konkursbehandling"] is True
    assert summary["under_avvikling"] is False


def test_build_risk_summary_empty_inputs():
    summary = build_risk_summary({"orgnr": "000000000"}, {}, {}, {})
    assert summary["risk_score"] is None
    assert summary["pep_hits"] == 0
    assert summary["risk_flags"] == []
    assert summary["risk_factors"] == []
