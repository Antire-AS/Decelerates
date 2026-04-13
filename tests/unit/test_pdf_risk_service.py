"""Tests for api/services/pdf_risk.py — risk report PDF generation."""
import sys
from unittest.mock import MagicMock

sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.services.pdf_risk import (
    _score_label,
    _fmt_mnok,
    _risk_section_title,
    _risk_row,
    _add_risk_cover,
    _add_risk_company_profile,
    _add_risk_financials,
    _add_risk_factors_table,
    generate_risk_report_pdf,
)


def _pdf():
    m = MagicMock()
    m.get_y.return_value = 50.0
    return m


# ── Pure function tests ──────────────────────────────────────────────────────

def test_score_label_lav():
    assert _score_label(0) == "Lav"
    assert _score_label(3) == "Lav"


def test_score_label_moderat():
    assert _score_label(4) == "Moderat"
    assert _score_label(7) == "Moderat"


def test_score_label_hoy():
    assert _score_label(8) == "Høy"
    assert _score_label(11) == "Høy"


def test_score_label_svaert_hoy():
    assert _score_label(12) == "Svært høy"
    assert _score_label(20) == "Svært høy"


def test_fmt_mnok_none():
    assert _fmt_mnok(None) == "–"


def test_fmt_mnok_value():
    result = _fmt_mnok(50_000_000)
    assert "50" in result
    assert "MNOK" in result


def test_fmt_mnok_zero():
    result = _fmt_mnok(0)
    assert "0" in result
    assert "MNOK" in result


# ── Builder tests ────────────────────────────────────────────────────────────

def test_risk_section_title():
    pdf = _pdf()
    _risk_section_title(pdf, "Test Section")
    assert pdf.cell.called
    assert pdf.line.called


def test_risk_row():
    pdf = _pdf()
    _risk_row(pdf, "Label", "Value")
    assert pdf.cell.called


def test_risk_row_bold():
    pdf = _pdf()
    _risk_row(pdf, "Label", "Bold Value", bold_value=True)
    pdf.set_font.assert_any_call("Helvetica", "B", 10)


def test_add_risk_cover():
    pdf = _pdf()
    _add_risk_cover(pdf, "Test AS", "123456789", "01.01.2026", 5, "Moderat")
    assert pdf.set_fill_color.called
    assert pdf.cell.called


def test_add_risk_cover_high():
    pdf = _pdf()
    _add_risk_cover(pdf, "X", "1", "d", 14, "Svært høy")
    assert pdf.cell.called


def test_add_risk_company_profile():
    pdf = _pdf()
    _add_risk_company_profile(pdf, "A AS", "123", "AS", "62", "IT", "Oslo", "2020-01-01")
    assert pdf.cell.called


def test_add_risk_company_profile_nulls():
    pdf = _pdf()
    _add_risk_company_profile(pdf, "A", "1", None, None, None, None, None)
    assert pdf.cell.called


def test_add_risk_financials():
    pdf = _pdf()
    regn = {"aarsresultat": 5_000_000, "sum_gjeld": 10_000_000, "antall_ansatte": 50}
    risk = {"equity_ratio": 0.35}
    _add_risk_financials(pdf, 100_000_000, 35_000_000, 80_000_000, regn, risk)
    assert pdf.cell.called


def test_add_risk_financials_nulls():
    pdf = _pdf()
    _add_risk_financials(pdf, None, None, None, {}, {"equity_ratio": None})
    assert pdf.cell.called


def test_add_risk_factors_table():
    pdf = _pdf()
    risk = {"factors": [
        {"label": "Negativ EK", "category": "Finansiell", "points": 3},
        {"label": "Ung bedrift", "category": "Alder", "points": 1},
    ]}
    _add_risk_factors_table(pdf, risk, 4, "Moderat")
    assert pdf.cell.called


# ── Orchestrator ─────────────────────────────────────────────────────────────

def test_generate_risk_report_pdf_returns_bytes():
    """Test with real FPDF since _RiskPDF subclass makes mocking complex."""
    risk = {
        "score": 6,
        "factors": [{"label": "Test", "category": "Cat", "points": 2}],
        "equity_ratio": 0.30,
    }
    regn = {"aarsresultat": 1_000_000, "sum_gjeld": 5_000_000, "antall_ansatte": 10}
    result = generate_risk_report_pdf(
        orgnr="123456789", navn="Test AS",
        organisasjonsform_kode="AS", kommune="Oslo",
        naeringskode1="62.010", naeringskode1_beskrivelse="IT",
        stiftelsesdato="2020-01-01",
        sum_driftsinntekter=50_000_000, sum_egenkapital=15_000_000,
        sum_eiendeler=40_000_000, regn=regn, risk=risk,
    )
    assert isinstance(result, bytes)
    assert len(result) > 0


