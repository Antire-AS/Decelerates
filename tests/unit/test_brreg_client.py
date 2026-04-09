"""Unit tests for api/services/brreg_client.py.

Pure tests — `requests` is monkey-patched at the module level so no network
hits the wire. Coverage target: 90%+ of brreg_client.py, with the relevance
sort and the regnskap extractors getting the most attention because they
are the parts where a regression is silent and only shows up in the UI
(see UI audit F02 for the kind of bug this is meant to catch).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from api.services import brreg_client
from api.services.brreg_client import (
    _build_enhet_dict,
    _build_regnskap_row,
    _deduplicate_by_year,
    _extract_balanse,
    _extract_eiendeler,
    _extract_periode,
    _extract_resultat,
    _extract_virksomhet,
    _pick_latest_regnskap,
    _relevance_score,
    fetch_board_members,
    fetch_company_struktur,
    fetch_enhet_by_orgnr,
    fetch_enhetsregisteret,
    fetch_regnskap_history,
    fetch_regnskap_keyfigures,
)


# ── _build_enhet_dict ─────────────────────────────────────────────────────────

def test_build_enhet_dict_full():
    raw = {
        "organisasjonsnummer": "123456789",
        "navn": "TEST AS",
        "organisasjonsform": {"beskrivelse": "Aksjeselskap", "kode": "AS"},
        "forretningsadresse": {
            "kommune": "OSLO",
            "postnummer": "0150",
            "land": "Norge",
            "kommunenummer": "0301",
            "poststed": "OSLO",
            "adresse": ["Storgata 1"],
        },
        "naeringskode1": {"kode": "62.010", "beskrivelse": "Programmering"},
    }
    out = _build_enhet_dict(raw)
    assert out["orgnr"] == "123456789"
    assert out["navn"] == "TEST AS"
    assert out["organisasjonsform"] == "Aksjeselskap"
    assert out["organisasjonsform_kode"] == "AS"
    assert out["kommune"] == "OSLO"
    assert out["naeringskode1_beskrivelse"] == "Programmering"
    # _addr is private and used downstream by fetch_enhet_by_orgnr
    assert out["_addr"]["kommunenummer"] == "0301"


def test_build_enhet_dict_missing_fields():
    """Empty input should not raise — every nested key is `or {}`-guarded."""
    out = _build_enhet_dict({})
    assert out["orgnr"] is None
    assert out["organisasjonsform"] is None
    assert out["_addr"] == {}


# ── _relevance_score ──────────────────────────────────────────────────────────

def test_relevance_exact_match_wins():
    exact      = {"navn": "DNB", "organisasjonsform_kode": "AS"}
    starts     = {"navn": "DNB BANK ASA", "organisasjonsform_kode": "ASA"}
    contains   = {"navn": "TANDEM DNB AS", "organisasjonsform_kode": "AS"}
    rows = sorted([starts, contains, exact],
                  key=lambda r: _relevance_score(r, "DNB"), reverse=True)
    assert rows[0] is exact


def test_relevance_starts_with_beats_contains():
    starts   = {"navn": "DNB BANK ASA", "organisasjonsform_kode": "ASA"}
    contains = {"navn": "BIG DNB AS",   "organisasjonsform_kode": "AS"}
    rows = sorted([contains, starts],
                  key=lambda r: _relevance_score(r, "DNB"), reverse=True)
    assert rows[0] is starts


def test_relevance_org_form_priority():
    """When two rows tie on text match, ASA outranks FLI outranks UTLA."""
    asa  = {"navn": "DNB BANK ASA",          "organisasjonsform_kode": "ASA"}
    fli  = {"navn": "DNB BEDRIFTSIDRETTSLAG","organisasjonsform_kode": "FLI"}
    utla = {"navn": "DNB MONCHEBANK",        "organisasjonsform_kode": "UTLA"}
    rows = sorted([fli, utla, asa],
                  key=lambda r: _relevance_score(r, "DNB"), reverse=True)
    assert rows == [asa, fli, utla]


def test_relevance_shorter_name_wins_within_bucket():
    """Same prefix + same org-form → shorter name ranks higher."""
    short = {"navn": "DNB BANK",          "organisasjonsform_kode": "ASA"}
    long  = {"navn": "DNB BANK NORGE ASA","organisasjonsform_kode": "ASA"}
    rows = sorted([long, short],
                  key=lambda r: _relevance_score(r, "DNB"), reverse=True)
    assert rows[0] is short


def test_relevance_unknown_org_form_defaults_to_zero():
    """Org form not in the priority table doesn't crash, falls back to 0."""
    weird = {"navn": "DNB SOMETHING", "organisasjonsform_kode": "ZZZ"}
    score = _relevance_score(weird, "DNB")
    assert score[3] == 0  # form_score slot


def test_relevance_handles_missing_fields():
    """Missing navn / organisasjonsform_kode shouldn't raise."""
    score = _relevance_score({}, "DNB")
    assert score == (0, 0, 0, 0, 0)


# ── fetch_enhetsregisteret ────────────────────────────────────────────────────

def _enhet(navn: str, code: str = "AS", orgnr: str = "111") -> dict:
    return {
        "organisasjonsnummer": orgnr,
        "navn": navn,
        "organisasjonsform": {"beskrivelse": code, "kode": code},
        "forretningsadresse": {"kommune": "OSLO"},
    }


@patch("api.services.brreg_client.requests.get")
def test_fetch_enhetsregisteret_sorts_by_relevance(mock_get):
    """The DNB-style scenario from UI audit F02."""
    mock_get.return_value = SimpleNamespace(
        status_code=200,
        json=lambda: {"_embedded": {"enheter": [
            _enhet("DNB BEDRIFTSIDRETTSLAG", "FLI", "1"),
            _enhet("DNB BANK ASA",            "ASA", "2"),
            _enhet("DNB EIENDOM AS",          "AS",  "3"),
            _enhet("DNB MONCHEBANK",          "UTLA","4"),
        ]}},
        raise_for_status=lambda: None,
    )
    results = fetch_enhetsregisteret("DNB")
    names = [r["navn"] for r in results]
    assert names[0] == "DNB BANK ASA"
    assert names[-1] == "DNB MONCHEBANK"


@patch("api.services.brreg_client.requests.get")
def test_fetch_enhetsregisteret_strips_private_addr(mock_get):
    mock_get.return_value = SimpleNamespace(
        status_code=200,
        json=lambda: {"_embedded": {"enheter": [_enhet("Test AS")]}},
        raise_for_status=lambda: None,
    )
    out = fetch_enhetsregisteret("Test")
    assert "_addr" not in out[0]


@patch("api.services.brreg_client.requests.get")
def test_fetch_enhetsregisteret_passes_kommunenummer(mock_get):
    mock_get.return_value = SimpleNamespace(
        status_code=200,
        json=lambda: {"_embedded": {"enheter": []}},
        raise_for_status=lambda: None,
    )
    fetch_enhetsregisteret("Test", kommunenummer="0301", size=5)
    args, kwargs = mock_get.call_args
    assert kwargs["params"] == {"navn": "Test", "size": 5, "kommunenummer": "0301"}


@patch("api.services.brreg_client.requests.get")
def test_fetch_enhetsregisteret_empty(mock_get):
    mock_get.return_value = SimpleNamespace(
        status_code=200, json=lambda: {}, raise_for_status=lambda: None,
    )
    assert fetch_enhetsregisteret("Test") == []


# ── fetch_enhet_by_orgnr ──────────────────────────────────────────────────────

@patch("api.services.brreg_client.requests.get")
def test_fetch_enhet_by_orgnr_404(mock_get):
    mock_get.return_value = SimpleNamespace(status_code=404)
    assert fetch_enhet_by_orgnr("111") is None


@patch("api.services.brreg_client.requests.get")
def test_fetch_enhet_by_orgnr_empty_embedded(mock_get):
    mock_get.return_value = SimpleNamespace(
        status_code=200,
        json=lambda: {"_embedded": {"enheter": []}},
        raise_for_status=lambda: None,
    )
    assert fetch_enhet_by_orgnr("111") is None


@patch("api.services.brreg_client.requests.get")
def test_fetch_enhet_by_orgnr_full(mock_get):
    raw = {
        "organisasjonsnummer": "984851006",
        "navn": "DNB BANK ASA",
        "organisasjonsform": {"beskrivelse": "Allmennaksjeselskap", "kode": "ASA"},
        "forretningsadresse": {
            "kommune": "OSLO",
            "kommunenummer": "0301",
            "poststed": "OSLO",
            "adresse": ["Dronning Eufemias gate 30"],
        },
        "naeringskode1": {"kode": "64.190"},
        "stiftelsesdato": "2003-10-10",
        "hjemmeside": "www.dnb.no",
        "konkurs": False,
        "underAvvikling": False,
    }
    mock_get.return_value = SimpleNamespace(
        status_code=200,
        json=lambda: {"_embedded": {"enheter": [raw]}},
        raise_for_status=lambda: None,
    )
    out = fetch_enhet_by_orgnr("984851006")
    assert out["orgnr"] == "984851006"
    assert out["adresse"] == ["Dronning Eufemias gate 30"]
    assert out["hjemmeside"] == "www.dnb.no"
    assert out["under_avvikling"] is False


# ── _pick_latest_regnskap + extractors ────────────────────────────────────────

def test_pick_latest_regnskap_picks_max_year():
    rs = [
        {"regnskapsperiode": {"tilDato": "2020-12-31"}, "id": "old"},
        {"regnskapsperiode": {"tilDato": "2024-12-31"}, "id": "new"},
        {"regnskapsperiode": {"tilDato": "2022-12-31"}, "id": "mid"},
    ]
    assert _pick_latest_regnskap(rs)["id"] == "new"


def test_pick_latest_regnskap_handles_invalid_dates():
    rs = [
        {"regnskapsperiode": {"tilDato": "bogus"}, "id": "bad"},
        {"regnskapsperiode": {"tilDato": "2024-12-31"}, "id": "good"},
    ]
    assert _pick_latest_regnskap(rs)["id"] == "good"


def test_extract_periode_full():
    out = _extract_periode({
        "regnskapsperiode": {"tilDato": "2024-12-31", "fraDato": "2024-01-01"},
        "valuta": "NOK",
        "id": "abc",
    })
    assert out["regnskapsår"] == 2024
    assert out["valuta"] == "NOK"
    assert out["id"] == "abc"


def test_extract_periode_invalid_date():
    out = _extract_periode({"regnskapsperiode": {"tilDato": "bogus"}})
    assert out["regnskapsår"] is None


def test_extract_virksomhet_handles_typo_key():
    """The legacy 'regnkapsprinsipper' typo key should also work."""
    out = _extract_virksomhet({
        "virksomhet": {"organisasjonsnummer": "111"},
        "regnkapsprinsipper": {"smaaForetak": True},
    })
    assert out["smaa_foretak"] is True


def test_extract_resultat_nested():
    raw = {"resultatregnskapResultat": {
        "driftsresultat": {
            "driftsinntekter": {"sumDriftsinntekter": 100},
            "driftskostnad": {"sumDriftskostnad": 60},
            "driftsresultat": 40,
        },
        "aarsresultat": 30,
    }}
    out = _extract_resultat(raw)
    assert out["sum_driftsinntekter"] == 100
    assert out["aarsresultat"] == 30


def test_extract_balanse_nested():
    raw = {"egenkapitalGjeld": {
        "sumEgenkapitalGjeld": 1000,
        "egenkapital": {"sumEgenkapital": 400},
        "gjeldOversikt": {
            "kortsiktigGjeld": {"sumKortsiktigGjeld": 200},
            "langsiktigGjeld": {"sumLangsiktigGjeld": 400},
        },
    }}
    out = _extract_balanse(raw)
    assert out["sum_egenkapital"] == 400
    assert out["sum_kortsiktig_gjeld"] == 200


def test_extract_eiendeler():
    raw = {"eiendeler": {"sumEiendeler": 1000, "goodwill": 50}}
    out = _extract_eiendeler(raw)
    assert out["sum_eiendeler"] == 1000
    assert out["goodwill"] == 50


# ── _deduplicate_by_year ──────────────────────────────────────────────────────

def test_deduplicate_prefers_selskap_over_konsern():
    rs = [
        {"regnskapsperiode": {"tilDato": "2024-12-31"}, "regnskapstype": "KONSERN", "id": "k"},
        {"regnskapsperiode": {"tilDato": "2024-12-31"}, "regnskapstype": "SELSKAP", "id": "s"},
    ]
    out = _deduplicate_by_year(rs)
    assert out[2024]["id"] == "s"


def test_deduplicate_skips_invalid_dates():
    rs = [
        {"regnskapsperiode": {"tilDato": "bogus"}},
        {"regnskapsperiode": {"tilDato": "2024-12-31"}, "id": "ok"},
    ]
    out = _deduplicate_by_year(rs)
    assert list(out.keys()) == [2024]


# ── _build_regnskap_row ───────────────────────────────────────────────────────

def test_build_regnskap_row_computes_equity_ratio():
    r = {
        "egenkapitalGjeld": {
            "sumEgenkapitalGjeld": 1000,
            "egenkapital": {"sumEgenkapital": 400},
        },
        "eiendeler": {"sumEiendeler": 1000},
    }
    row = _build_regnskap_row(2024, r)
    assert row["equity_ratio"] == 0.4


def test_build_regnskap_row_handles_zero_assets():
    r = {
        "egenkapitalGjeld": {"egenkapital": {"sumEgenkapital": 100}},
        "eiendeler": {"sumEiendeler": 0},
    }
    row = _build_regnskap_row(2024, r)
    assert row["equity_ratio"] is None


# ── fetch_regnskap_keyfigures ─────────────────────────────────────────────────

@patch("api.services.brreg_client.requests.get")
def test_fetch_regnskap_keyfigures_404(mock_get):
    mock_get.return_value = SimpleNamespace(status_code=404)
    assert fetch_regnskap_keyfigures("111") == {}


@patch("api.services.brreg_client.requests.get")
def test_fetch_regnskap_keyfigures_empty_list(mock_get):
    mock_get.return_value = SimpleNamespace(
        status_code=200, json=lambda: [], raise_for_status=lambda: None,
    )
    assert fetch_regnskap_keyfigures("111") == {}


@patch("api.services.brreg_client.requests.get")
def test_fetch_regnskap_keyfigures_picks_latest(mock_get):
    mock_get.return_value = SimpleNamespace(
        status_code=200,
        raise_for_status=lambda: None,
        json=lambda: [
            {"regnskapsperiode": {"tilDato": "2023-12-31"}, "valuta": "NOK", "id": "old"},
            {"regnskapsperiode": {"tilDato": "2024-12-31"}, "valuta": "USD", "id": "new"},
        ],
    )
    out = fetch_regnskap_keyfigures("111")
    assert out["regnskapsår"] == 2024
    assert out["valuta"] == "USD"
    assert out["id"] == "new"


# ── fetch_regnskap_history ────────────────────────────────────────────────────

@patch("api.services.brreg_client.requests.get")
def test_fetch_regnskap_history_404(mock_get):
    mock_get.return_value = SimpleNamespace(status_code=404)
    assert fetch_regnskap_history("111") == []


@patch("api.services.brreg_client.requests.get")
def test_fetch_regnskap_history_returns_sorted_years(mock_get):
    mock_get.return_value = SimpleNamespace(
        status_code=200, raise_for_status=lambda: None,
        json=lambda: [
            {"regnskapsperiode": {"tilDato": "2024-12-31"}, "regnskapstype": "SELSKAP"},
            {"regnskapsperiode": {"tilDato": "2022-12-31"}, "regnskapstype": "SELSKAP"},
            {"regnskapsperiode": {"tilDato": "2023-12-31"}, "regnskapstype": "SELSKAP"},
        ],
    )
    rows = fetch_regnskap_history("111")
    assert [r["year"] for r in rows] == [2022, 2023, 2024]


# ── fetch_company_struktur ────────────────────────────────────────────────────

@patch("api.services.brreg_client.requests.get")
def test_fetch_company_struktur_with_parent_and_subs(mock_get):
    """First call: enhet with overordnetEnhet. Second: parent enhet. Third: underenheter list."""
    def fake_get(url, *a, **k):
        if url.endswith("/CHILD"):
            return SimpleNamespace(ok=True, json=lambda: {"overordnetEnhet": "PARENT"})
        if url.endswith("/PARENT"):
            return SimpleNamespace(ok=True, json=lambda: {
                "organisasjonsnummer": "PARENT",
                "navn": "Parent AS",
                "organisasjonsform": {"beskrivelse": "Aksjeselskap"},
                "forretningsadresse": {"kommune": "OSLO"},
            })
        if url.endswith("/CHILD/underenheter"):
            return SimpleNamespace(ok=True, json=lambda: {
                "_embedded": {"underenheter": [
                    {"organisasjonsnummer": "U1", "navn": "Sub 1", "antallAnsatte": 5,
                     "beliggenhetsadresse": {"kommune": "BERGEN"}},
                ]},
                "page": {"totalElements": 1},
            })
        return SimpleNamespace(ok=False)

    mock_get.side_effect = fake_get
    out = fetch_company_struktur("CHILD")
    assert out["parent"]["orgnr"] == "PARENT"
    assert out["parent"]["navn"] == "Parent AS"
    assert out["total_sub_units"] == 1
    assert out["sub_units"][0]["navn"] == "Sub 1"


@patch("api.services.brreg_client.requests.get")
def test_fetch_company_struktur_no_parent(mock_get):
    mock_get.return_value = SimpleNamespace(
        ok=True, json=lambda: {"_embedded": {"underenheter": []}, "page": {"totalElements": 0}},
    )
    out = fetch_company_struktur("ROOT")
    assert out["parent"] is None
    assert out["total_sub_units"] == 0


@patch("api.services.brreg_client.requests.get")
def test_fetch_company_struktur_swallows_exceptions(mock_get):
    """Network failures are logged, never raised — UI must always render."""
    mock_get.side_effect = Exception("network down")
    out = fetch_company_struktur("ANY")
    assert out == {"parent": None, "sub_units": [], "total_sub_units": 0}


# ── fetch_board_members ───────────────────────────────────────────────────────

@patch("api.services.brreg_client.requests.get")
def test_fetch_board_members_404(mock_get):
    mock_get.return_value = SimpleNamespace(status_code=404)
    assert fetch_board_members("111") == []


@patch("api.services.brreg_client.requests.get")
def test_fetch_board_members_full(mock_get):
    mock_get.return_value = SimpleNamespace(
        status_code=200, raise_for_status=lambda: None,
        json=lambda: {"rollegrupper": [
            {"type": {"beskrivelse": "Styre"}, "roller": [
                {
                    "type": {"beskrivelse": "Styreleder"},
                    "person": {
                        "navn": {"fornavn": "Ola", "etternavn": "Nordmann"},
                        "fodselsdato": "1970-01-01",
                        "erDoed": False,
                    },
                    "fratraadt": False,
                },
            ]},
        ]},
    )
    members = fetch_board_members("111")
    assert len(members) == 1
    assert members[0]["name"] == "Ola Nordmann"
    assert members[0]["birth_year"] == 1970
    assert members[0]["role"] == "Styreleder"
    assert members[0]["resigned"] is False
