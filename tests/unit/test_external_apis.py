"""Unit tests for services/external_apis.py — pure data-transform functions, no HTTP."""

from api.services.external_apis import (
    _pick_latest_regnskap,
    _extract_resultat,
    _extract_balanse,
    _extract_eiendeler,
    _nace_to_section,
    fetch_ssb_benchmark,
)


# ── _pick_latest_regnskap ─────────────────────────────────────────────────────


def test_pick_latest_regnskap():
    regnskaper = [
        {"regnskapsperiode": {"tilDato": "2021-12-31"}, "aarsresultat": 100},
        {"regnskapsperiode": {"tilDato": "2023-12-31"}, "aarsresultat": 300},
        {"regnskapsperiode": {"tilDato": "2022-12-31"}, "aarsresultat": 200},
    ]
    result = _pick_latest_regnskap(regnskaper)
    assert result["aarsresultat"] == 300


# ── _extract_resultat ─────────────────────────────────────────────────────────


def test_extract_resultat_full():
    chosen = {
        "resultatregnskapResultat": {
            "driftsresultat": {
                "driftsinntekter": {
                    "salgsinntekter": 900_000,
                    "sumDriftsinntekter": 1_000_000,
                },
                "driftskostnad": {
                    "loennskostnad": 400_000,
                    "sumDriftskostnad": 700_000,
                },
                "driftsresultat": 300_000,
            },
            "finansresultat": {
                "finansinntekt": {"sumFinansinntekter": 10_000},
                "finanskostnad": {
                    "annenRentekostnad": 5_000,
                    "sumFinanskostnad": 5_000,
                },
                "nettoFinans": 5_000,
            },
            "aarsresultat": 280_000,
            "totalresultat": 280_000,
        }
    }
    result = _extract_resultat(chosen)
    assert result["sum_driftsinntekter"] == 1_000_000
    assert result["salgsinntekter"] == 900_000
    assert result["loennskostnad"] == 400_000
    assert result["driftsresultat"] == 300_000
    assert result["aarsresultat"] == 280_000
    assert result["sum_finansinntekt"] == 10_000
    assert result["sum_finanskostnad"] == 5_000


# ── _extract_balanse ──────────────────────────────────────────────────────────


def test_extract_balanse_full():
    chosen = {
        "egenkapitalGjeld": {
            "egenkapital": {
                "innskuttEgenkapital": {"sumInnskuttEgenkapital": 100_000},
                "opptjentEgenkapital": {"sumOpptjentEgenkapital": 50_000},
                "sumEgenkapital": 150_000,
            },
            "gjeldOversikt": {
                "kortsiktigGjeld": {"sumKortsiktigGjeld": 80_000},
                "langsiktigGjeld": {"sumLangsiktigGjeld": 120_000},
                "sumGjeld": 200_000,
            },
            "sumEgenkapitalGjeld": 350_000,
        }
    }
    result = _extract_balanse(chosen)
    assert result["sum_egenkapital"] == 150_000
    assert result["sum_innskutt_egenkapital"] == 100_000
    assert result["sum_opptjent_egenkapital"] == 50_000
    assert result["sum_kortsiktig_gjeld"] == 80_000
    assert result["sum_langsiktig_gjeld"] == 120_000
    assert result["sum_gjeld"] == 200_000
    assert result["sum_egenkapital_gjeld"] == 350_000


# ── _extract_eiendeler ────────────────────────────────────────────────────────


def test_extract_eiendeler_full():
    chosen = {
        "eiendeler": {
            "omloepsmidler": {"sumOmloepsmidler": 120_000},
            "anleggsmidler": {"sumAnleggsmidler": 380_000},
            "sumEiendeler": 500_000,
            "sumVarer": 30_000,
            "sumFordringer": 50_000,
            "sumInvesteringer": 20_000,
            "sumBankinnskuddOgKontanter": 20_000,
            "goodwill": 10_000,
        }
    }
    result = _extract_eiendeler(chosen)
    assert result["sum_eiendeler"] == 500_000
    assert result["sum_omloepsmidler"] == 120_000
    assert result["sum_anleggsmidler"] == 380_000
    assert result["goodwill"] == 10_000


# ── _nace_to_section ──────────────────────────────────────────────────────────


def test_nace_to_section_finance():
    # NACE 64.11 = Sentralbankvirksomhet → section K (64–66)
    assert _nace_to_section("64.11") == "K"


def test_nace_to_section_education():
    # NACE 85.10 = Førskoleopplæring → section P (85)
    assert _nace_to_section("85.10") == "P"


# ── fetch_ssb_benchmark ───────────────────────────────────────────────────────


def test_fetch_ssb_benchmark_no_nace_returns_none():
    result = fetch_ssb_benchmark("")
    assert result is None
