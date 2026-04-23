"""Unit tests for the anbudspakke PDF assembler + renderer.

Two layers:
  1. `build_anbudspakke_data` — orchestration against mocked DB. Verifies
     every section key is present even when subsections are empty, and
     that the NotFound path raises cleanly.
  2. `generate_anbudspakke_pdf` — renders a well-populated fixture to
     bytes and pins the PDF magic header so we catch any regression
     that breaks the output format.
"""

from __future__ import annotations

import importlib
import sys
from datetime import datetime, timezone
from typing import Any, List
from unittest.mock import patch

import pytest

from api.domain.exceptions import NotFoundError
from api.services.pdf_anbud import (
    _fmt_nok,
    _fmt_pct,
    _safe,
    build_anbudspakke_data,
    generate_anbudspakke_pdf,
)


@pytest.fixture(autouse=True)
def _restore_real_fpdf():
    """conftest stubs fpdf with MagicMock so unit tests run without the
    real package. The PDF-bytes assertions below need the real fpdf2
    (installed via pyproject.toml) to actually emit a PDF header."""
    sys.modules.pop("fpdf", None)
    real_fpdf = importlib.import_module("fpdf")
    sys.modules["fpdf"] = real_fpdf
    yield


# ── Formatters ──────────────────────────────────────────────────────────────


def test_fmt_nok_renders_mnok():
    assert _fmt_nok(86_537_000_000) == "86 537.0 MNOK"


def test_fmt_nok_handles_none():
    assert _fmt_nok(None) == "-"


def test_fmt_pct_renders_one_decimal():
    assert _fmt_pct(0.078) == "7.8%"


def test_fmt_pct_handles_none():
    assert _fmt_pct(None) == "-"


def test_safe_strips_non_latin_1():
    """fpdf2 uses latin-1 Helvetica by default; any char outside that set
    has to be transliterated before it hits the canvas or we get a
    UnicodeEncodeError crash mid-render."""
    assert "\u2019" not in _safe("don\u2019t")
    assert "..." in _safe("loading\u2026")
    assert "-" in _safe("priced \u2013 negotiable")


# ── Data assembler ──────────────────────────────────────────────────────────


class _FakeCompany:
    def __init__(self, orgnr: str, navn: str, **kw: Any) -> None:
        self.orgnr = orgnr
        self.navn = navn
        self.organisasjonsform_kode = kw.get("organisasjonsform_kode")
        self.naeringskode1 = kw.get("naeringskode1")
        self.naeringskode1_beskrivelse = kw.get("naeringskode1_beskrivelse")
        self.kommune = kw.get("kommune")
        self.land = kw.get("land")
        self.antall_ansatte = kw.get("antall_ansatte")
        self.regnskap_raw = kw.get("regnskap_raw", {})
        self.pep_raw = kw.get("pep_raw", {})
        self.sum_driftsinntekter = kw.get("sum_driftsinntekter")
        self.sum_eiendeler = kw.get("sum_eiendeler")
        self.sum_egenkapital = kw.get("sum_egenkapital")


class _FakeQuery:
    def __init__(self, result: Any = None) -> None:
        self._result = result

    def filter(self, *a: Any, **kw: Any) -> "_FakeQuery":
        return self

    def order_by(self, *a: Any, **kw: Any) -> "_FakeQuery":
        return self

    def limit(self, n: int) -> "_FakeQuery":
        return self

    def first(self) -> Any:
        return (
            self._result
            if not isinstance(self._result, list)
            else (self._result[0] if self._result else None)
        )

    def all(self) -> List[Any]:
        return self._result if isinstance(self._result, list) else []


class _FakeDB:
    def __init__(self, by_model: dict) -> None:
        self._by_model = by_model

    def query(self, *args: Any) -> _FakeQuery:
        name = getattr(
            args[0],
            "__name__",
            getattr(getattr(args[0], "class_", None), "__name__", ""),
        )
        return _FakeQuery(self._by_model.get(name))


def _common_patches():
    return [
        patch("api.services.pdf_anbud.compute_peer_benchmark", return_value=None),
        patch("api.services.pdf_anbud.fetch_board_members", return_value=[]),
        patch("api.services.pdf_anbud.estimate_insurance_needs", return_value=[]),
    ]


def test_build_raises_notfound_when_company_missing():
    db = _FakeDB({"Company": None})
    with pytest.raises(NotFoundError):
        build_anbudspakke_data("999999999", db)  # type: ignore[arg-type]


def test_build_returns_every_top_level_section():
    db = _FakeDB({"Company": _FakeCompany("123456789", "Acme AS")})
    patches = _common_patches()
    for p in patches:
        p.start()
    try:
        data = build_anbudspakke_data("123456789", db)  # type: ignore[arg-type]
    finally:
        for p in patches:
            p.stop()
    for key in (
        "orgnr",
        "generated_at",
        "selskap",
        "financials",
        "risk",
        "needs",
        "notes",
        "material_news",
        "policies",
    ):
        assert key in data
    assert data["orgnr"] == "123456789"
    assert data["selskap"]["navn"] == "Acme AS"


def test_build_includes_altman_in_risk_section_when_regn_has_fields():
    regn = {
        "sum_eiendeler": 1_000,
        "sum_gjeld": 400,
        "sum_egenkapital": 600,
        "driftsresultat": 150,
        "sum_opptjent_egenkapital": 300,
        "sum_omloepsmidler": 500,
        "short_term_debt": 150,
    }
    db = _FakeDB(
        {"Company": _FakeCompany("123456789", "Healthy AS", regnskap_raw=regn)}
    )
    patches = _common_patches()
    for p in patches:
        p.start()
    try:
        data = build_anbudspakke_data("123456789", db)  # type: ignore[arg-type]
    finally:
        for p in patches:
            p.stop()
    altman = data["risk"]["altman_z"]
    assert altman is not None
    assert altman["zone"] in {"safe", "grey", "distress"}


# ── PDF renderer ────────────────────────────────────────────────────────────


def _minimal_fixture() -> dict:
    return {
        "orgnr": "923609016",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "selskap": {
            "navn": "Equinor ASA",
            "orgnr": "923609016",
            "organisasjonsform_kode": "ASA",
            "naeringskode1": "06.100",
            "naeringskode1_beskrivelse": "Utvinning av raolje",
            "kommune": "Stavanger",
            "land": "Norge",
            "antall_ansatte": 22_000,
            "stiftelsesdato": "1972-07-14",
            "board_members": [{"name": "A Tester", "role": "Styreleder"}],
        },
        "financials": [
            {
                "year": 2024,
                "revenue": 72_543_000_000,
                "net_result": 8_141_000_000,
                "equity": 41_090_000_000,
                "total_assets": 109_150_000_000,
                "equity_ratio": 0.376,
                "antall_ansatte": 22_000,
            }
        ],
        "risk": {
            "rule_score": 9,
            "rule_factors": [
                {"label": "Hoy gjeldsgrad", "points": 2, "category": "Okonomi"},
            ],
            "equity_ratio": 0.376,
            "altman_z": {
                "z_score": 3.94,
                "zone": "safe",
                "score_20": 1,
                "components": {
                    "working_capital_ratio": 0.2,
                    "retained_earnings_ratio": 0.3,
                    "ebit_ratio": 0.1,
                    "equity_to_liab_ratio": 0.6,
                },
                "formula": "Altman Z''",
            },
            "peer": None,
            "pep_hits": 0,
        },
        "needs": [
            {
                "type": "Ansvarsforsikring",
                "anbefalt_sum": "100 MNOK",
                "prioritet": "Hoy",
            },
        ],
        "notes": [
            {"question": "Dekning?", "answer": "Global", "created_at": "2026-04-22"},
        ],
        "material_news": [],
        "policies": [
            {
                "id": 1,
                "product": "Ansvar",
                "insurer": "Gjensidige",
                "annual_premium_nok": 2_500_000,
                "end_date": "2026-12-31",
            }
        ],
    }


def test_generate_anbudspakke_pdf_returns_valid_pdf_bytes():
    out = generate_anbudspakke_pdf(_minimal_fixture())
    assert isinstance(out, bytes)
    assert out.startswith(b"%PDF-"), "PDF magic header missing"
    # Sanity: real PDFs are kilobytes. An empty renderer would still
    # produce the magic bytes but would fail this lower bound.
    assert len(out) > 1_000


def test_generate_tolerates_missing_altman():
    """Bank profile — no Altman block available, should still render."""
    fx = _minimal_fixture()
    fx["risk"]["altman_z"] = None
    out = generate_anbudspakke_pdf(fx)
    assert out.startswith(b"%PDF-")


def test_generate_tolerates_empty_optional_sections():
    fx = _minimal_fixture()
    fx["financials"] = []
    fx["needs"] = []
    fx["notes"] = []
    fx["material_news"] = []
    fx["policies"] = []
    out = generate_anbudspakke_pdf(fx)
    assert out.startswith(b"%PDF-")
