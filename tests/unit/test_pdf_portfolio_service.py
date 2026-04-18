"""Tests for api/services/pdf_portfolio.py — portfolio report PDF generation."""

import sys
from unittest.mock import MagicMock, patch

sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.services.pdf_portfolio import (
    _portfolio_cover,
    _portfolio_risk_table,
    _portfolio_alerts_section,
    _portfolio_concentration_section,
    generate_portfolio_pdf,
)


def _pdf():
    m = MagicMock()
    m.get_y.return_value = 50.0
    m.w = 297  # landscape A4
    m.l_margin = 15
    m.r_margin = 15
    return m


# ── Builder tests ────────────────────────────────────────────────────────────


def test_portfolio_cover_basic():
    pdf = _pdf()
    _portfolio_cover(pdf, "Min Portefolje", {"firm_name": "Megler AS"}, "01.01.2026")
    pdf.add_page.assert_called_once()
    assert pdf.cell.called


def test_portfolio_cover_with_contact():
    pdf = _pdf()
    _portfolio_cover(pdf, "P", {"firm_name": "M", "contact_name": "Ola"}, "01.01.2026")
    # Should render contact_name cell
    assert pdf.cell.call_count >= 4


def test_portfolio_risk_table_empty():
    pdf = _pdf()
    _portfolio_risk_table(pdf, [])
    assert pdf.cell.called  # headers still rendered


def test_portfolio_risk_table_with_companies():
    pdf = _pdf()
    companies = [
        {
            "navn": "A AS",
            "orgnr": "111",
            "sum_driftsinntekter": 50_000_000,
            "antall_ansatte": 20,
            "egenkapitalandel": 0.35,
            "risk_score": 5,
        },
        {
            "navn": "B AS",
            "orgnr": "222",
            "omsetning": 200_000_000,
            "equity_ratio": 0.10,
            "risk_score": 14,
        },
        {"navn": "C AS", "orgnr": "333", "risk_score": None},
    ]
    _portfolio_risk_table(pdf, companies)
    assert pdf.cell.called
    assert pdf.ln.called


def test_portfolio_risk_table_low_score():
    pdf = _pdf()
    _portfolio_risk_table(pdf, [{"navn": "X", "orgnr": "1", "risk_score": 2}])
    assert pdf.cell.called


def test_portfolio_alerts_section_empty():
    pdf = _pdf()
    _portfolio_alerts_section(pdf, [])
    # Should return early — no section title
    assert not pdf.cell.called


def test_portfolio_alerts_section_with_alerts():
    pdf = _pdf()
    alerts = [
        {
            "severity": "Kritisk",
            "navn": "A AS",
            "alert_type": "Konkurs",
            "detail": "Under avvikling",
        },
        {"severity": "Moderat", "navn": "B AS", "alert_type": "EK", "detail": "Lav EK"},
    ]
    _portfolio_alerts_section(pdf, alerts)
    assert pdf.cell.called


def test_portfolio_alerts_section_hoy_severity():
    pdf = _pdf()
    alerts = [{"severity": "Hoy", "navn": "X", "alert_type": "T", "detail": "D"}]
    _portfolio_alerts_section(pdf, alerts)
    assert pdf.set_fill_color.called


def test_portfolio_concentration_section():
    pdf = _pdf()
    concentration = {
        "total_revenue": 5_000_000_000,
        "by_industry": [
            {"section": "G", "label": "Handel", "count": 10, "revenue": 1_000_000_000}
        ],
        "by_geography": [{"kommune": "Oslo", "count": 15}],
        "by_size": [{"band": "SMB", "count": 8}],
    }
    _portfolio_concentration_section(pdf, concentration)
    assert pdf.cell.called


def test_portfolio_concentration_section_empty():
    pdf = _pdf()
    _portfolio_concentration_section(pdf, {"total_revenue": 0})
    assert pdf.cell.called


# ── Orchestrator ─────────────────────────────────────────────────────────────


@patch("api.services.pdf_portfolio.FPDF")
def test_generate_portfolio_pdf_returns_bytes(mock_fpdf_cls):
    mock_pdf = MagicMock()
    mock_buf = MagicMock()
    mock_buf.getvalue.return_value = b"%PDF-portfolio"
    mock_pdf.get_y.return_value = 50.0
    mock_pdf.w = 297
    mock_pdf.l_margin = 15
    mock_pdf.r_margin = 15
    mock_pdf.output = MagicMock()  # pdf.output(buf)
    mock_fpdf_cls.return_value = mock_pdf

    with patch("api.services.pdf_portfolio.io.BytesIO", return_value=mock_buf):
        result = generate_portfolio_pdf(
            portfolio_name="Test",
            companies=[],
            alerts=[],
            concentration={},
            broker={"firm_name": "M"},
        )
    assert result == b"%PDF-portfolio"


@patch("api.services.pdf_portfolio.FPDF")
def test_generate_portfolio_pdf_with_alerts_and_concentration(mock_fpdf_cls):
    mock_pdf = MagicMock()
    mock_buf = MagicMock()
    mock_buf.getvalue.return_value = b"%PDF-full"
    mock_pdf.get_y.return_value = 100.0  # low enough to not trigger page break
    mock_pdf.w = 297
    mock_pdf.l_margin = 15
    mock_pdf.r_margin = 15
    mock_fpdf_cls.return_value = mock_pdf

    with patch("api.services.pdf_portfolio.io.BytesIO", return_value=mock_buf):
        result = generate_portfolio_pdf(
            portfolio_name="Full",
            companies=[{"navn": "A", "orgnr": "1", "risk_score": 5}],
            alerts=[
                {"severity": "Kritisk", "navn": "A", "alert_type": "X", "detail": "Y"}
            ],
            concentration={
                "total_revenue": 1e9,
                "by_industry": [],
                "by_geography": [],
                "by_size": [],
            },
            broker={"firm_name": "M"},
        )
    assert result == b"%PDF-full"


@patch("api.services.pdf_portfolio.FPDF")
def test_generate_portfolio_pdf_alerts_page_break(mock_fpdf_cls):
    mock_pdf = MagicMock()
    mock_buf = MagicMock()
    mock_buf.getvalue.return_value = b"%PDF"
    mock_pdf.get_y.return_value = 170.0  # triggers page break (> 160)
    mock_pdf.w = 297
    mock_pdf.l_margin = 15
    mock_pdf.r_margin = 15
    mock_fpdf_cls.return_value = mock_pdf

    with patch("api.services.pdf_portfolio.io.BytesIO", return_value=mock_buf):
        generate_portfolio_pdf(
            portfolio_name="P",
            companies=[],
            alerts=[
                {"severity": "Moderat", "navn": "X", "alert_type": "T", "detail": "D"}
            ],
            concentration=None,
            broker={"firm_name": "M"},
        )
    # add_page called: once in cover, once after cover, once for alert page break
    assert mock_pdf.add_page.call_count >= 3
