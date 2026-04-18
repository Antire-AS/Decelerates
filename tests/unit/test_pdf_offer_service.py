"""Tests for api/services/pdf_offer.py — forsikringstilbud PDF generation."""

import sys
from unittest.mock import MagicMock, patch

sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.services.pdf_offer import (
    _priority_color,
    _extract_offer_summary,
    _build_tilbud_broker_header,
    _build_client_company_info,
    _build_client_summary_and_premium,
    _build_tilbud_client_box,
    _build_tilbud_forside,
    _build_offers_comparison_table,
    _build_offers_strengths_section,
    _build_tilbud_offers_page,
    _build_coverage_table_header,
    _build_coverage_table_rows,
    _build_coverage_table_total,
    _build_tilbud_coverage_table,
    _build_detail_header,
    _build_detail_content,
    _build_tilbud_coverage_detail,
    _build_terms_bullets,
    _build_tilbud_terms_page,
    generate_forsikringstilbud_pdf,
)
from api.services.pdf_base import _DARK_BLUE, _MID_BLUE, _LIGHT_BLUE


def _pdf():
    m = MagicMock()
    m.get_y.return_value = 50.0
    return m


# ── Pure function tests ──────────────────────────────────────────────────────


def test_priority_color_maa():
    assert _priority_color("Må ha") == (200, 50, 50)


def test_priority_color_anbefalt():
    assert _priority_color("Anbefalt") == (220, 100, 30)


def test_priority_color_unknown():
    assert _priority_color("Valgfri") == (100, 100, 100)


def test_priority_color_none():
    assert _priority_color(None) == (100, 100, 100)


# ── LLM-backed extraction ───────────────────────────────────────────────────


def test_extract_offer_summary_empty_text():
    result = _extract_offer_summary("Gjensidige", "")
    assert result["selskap"] == "Gjensidige"
    assert result["premie"] == "–"


@patch(
    "api.services.pdf_offer._parse_json_from_llm_response",
    return_value={"premie": "50000 kr"},
)
@patch("api.services.pdf_offer._llm_answer_raw", return_value='{"premie": "50000 kr"}')
def test_extract_offer_summary_with_llm(mock_llm, mock_parse):
    result = _extract_offer_summary("If", "Premie totalt 50 000 kr per ar")
    assert result["selskap"] == "If"
    assert result["premie"] == "50000 kr"
    mock_llm.assert_called_once()


@patch("api.services.pdf_offer._parse_json_from_llm_response", return_value=None)
@patch("api.services.pdf_offer._llm_answer_raw", return_value=None)
def test_extract_offer_summary_llm_fails(mock_llm, mock_parse):
    result = _extract_offer_summary("Tryg", "Noe tekst her")
    assert result["selskap"] == "Tryg"
    assert "Noe tekst her" in result["dekning"]


# ── Builder functions (MagicMock pdf) ────────────────────────────────────────


def test_build_tilbud_broker_header():
    pdf = _pdf()
    _build_tilbud_broker_header(
        pdf, "Megler AS", "Ola N", "ola@m.no", "12345678", _DARK_BLUE
    )
    assert pdf.set_font.called
    assert pdf.cell.called


def test_build_tilbud_broker_header_no_contact():
    pdf = _pdf()
    _build_tilbud_broker_header(
        pdf, "Megler AS", "", "ola@m.no", "12345678", _DARK_BLUE
    )
    assert pdf.set_fill_color.called


def test_build_client_company_info():
    pdf = _pdf()
    _build_client_company_info(
        pdf,
        "Test AS",
        "123456789",
        "AS",
        "62.010",
        "IT",
        "Oslo",
        _DARK_BLUE,
        _LIGHT_BLUE,
    )
    assert pdf.rect.called


def test_build_client_summary_and_premium_with_sammendrag():
    pdf = _pdf()
    _build_client_summary_and_premium(
        pdf,
        "01.01.2026",
        "31.01.2026",
        3,
        "Sammendrag",
        "100 000 kr",
        _DARK_BLUE,
        _MID_BLUE,
    )
    assert pdf.multi_cell.called


def test_build_client_summary_and_premium_no_sammendrag():
    pdf = _pdf()
    _build_client_summary_and_premium(
        pdf, "01.01.2026", "31.01.2026", 0, "", "0 kr", _DARK_BLUE, _MID_BLUE
    )
    assert pdf.cell.called


def test_build_tilbud_client_box():
    pdf = _pdf()
    _build_tilbud_client_box(
        pdf,
        "A",
        "1",
        None,
        None,
        None,
        None,
        "d",
        "v",
        1,
        "",
        "1 kr",
        _DARK_BLUE,
        _MID_BLUE,
        _LIGHT_BLUE,
    )
    assert pdf.cell.called


def test_build_tilbud_forside():
    pdf = _pdf()
    recs = [
        {
            "type": "Ansvar",
            "prioritet": "Må ha",
            "anbefalt_sum": "1M",
            "begrunnelse": "x",
        }
    ]
    _build_tilbud_forside(
        pdf,
        "N",
        "1",
        None,
        None,
        None,
        None,
        "B",
        "C",
        "e",
        "p",
        "d",
        "v",
        recs,
        "",
        "1kr",
        _DARK_BLUE,
        _MID_BLUE,
        _LIGHT_BLUE,
    )
    pdf.add_page.assert_called_once()


def test_build_offers_comparison_table():
    pdf = _pdf()
    summaries = [
        {
            "selskap": "If",
            "premie": "50k",
            "dekning": "Alt",
            "egenandel": "10k",
            "vilkaar": "Ingen",
        }
    ]
    _build_offers_comparison_table(pdf, summaries, "01.01.2026", _DARK_BLUE)
    assert pdf.cell.called


def test_build_offers_strengths_section():
    pdf = _pdf()
    summaries = [
        {"selskap": "Gjensidige", "styrker": "God pris", "svakheter": "Lav dekning"}
    ]
    _build_offers_strengths_section(pdf, summaries, _DARK_BLUE, _MID_BLUE)
    assert pdf.multi_cell.called


def test_build_tilbud_offers_page():
    pdf = _pdf()
    summaries = [
        {
            "selskap": "X",
            "premie": "1",
            "dekning": "2",
            "egenandel": "3",
            "vilkaar": "4",
            "styrker": "a",
            "svakheter": "b",
        }
    ]
    _build_tilbud_offers_page(pdf, summaries, "01.01.2026", _DARK_BLUE, _MID_BLUE)
    pdf.add_page.assert_called_once()


def test_build_coverage_table_header():
    pdf = _pdf()
    _build_coverage_table_header(pdf, "Test AS", "123", "01.01.2026", _DARK_BLUE)
    assert pdf.cell.called


def test_build_coverage_table_rows():
    pdf = _pdf()
    recs = [
        {
            "type": "Brann",
            "prioritet": "Anbefalt",
            "anbefalt_sum": "500k",
            "begrunnelse": "Viktig",
        }
    ]
    _build_coverage_table_rows(pdf, recs, _priority_color)
    assert pdf.cell.called


def test_build_coverage_table_total():
    pdf = _pdf()
    _build_coverage_table_total(pdf, "100 000 kr", _DARK_BLUE)
    assert pdf.cell.called


def test_build_tilbud_coverage_table():
    pdf = _pdf()
    recs = [
        {"type": "X", "prioritet": "Må ha", "anbefalt_sum": "1", "begrunnelse": "y"}
    ]
    _build_tilbud_coverage_table(
        pdf, "N", "1", recs, "100k", "d", _DARK_BLUE, _priority_color
    )
    pdf.add_page.assert_called_once()


def test_build_detail_header():
    pdf = _pdf()
    rec = {"type": "Ansvar", "prioritet": "Må ha"}
    _build_detail_header(pdf, rec, _MID_BLUE, _priority_color)
    assert pdf.set_fill_color.called


def test_build_detail_content():
    pdf = _pdf()
    rec = {"anbefalt_sum": "1M", "begrunnelse": "Stor risiko"}
    _build_detail_content(pdf, rec)
    assert pdf.multi_cell.called


def test_build_tilbud_coverage_detail():
    pdf = _pdf()
    rec = {
        "type": "T",
        "prioritet": "Anbefalt",
        "anbefalt_sum": "1",
        "begrunnelse": "b",
    }
    _build_tilbud_coverage_detail(pdf, rec, _MID_BLUE, _priority_color)
    pdf.add_page.assert_called_once()


def test_build_terms_bullets():
    pdf = _pdf()
    _build_terms_bullets(pdf, "Megler AS", "01.01.2026")
    assert pdf.multi_cell.called


def test_build_tilbud_terms_page():
    pdf = _pdf()
    _build_tilbud_terms_page(pdf, "N", "1", "B", "C", "P", "d", _DARK_BLUE, _MID_BLUE)
    pdf.add_page.assert_called_once()


# ── Orchestrator ─────────────────────────────────────────────────────────────


@patch("api.services.pdf_offer.FPDF")
def test_generate_forsikringstilbud_pdf_returns_bytes(mock_fpdf_cls):
    mock_pdf = MagicMock()
    mock_pdf.output.return_value = b"%PDF-fake"
    mock_pdf.get_y.return_value = 50.0
    mock_fpdf_cls.return_value = mock_pdf

    result = generate_forsikringstilbud_pdf(
        orgnr="123456789",
        navn="Test AS",
        organisasjonsform_kode="AS",
        naeringskode1="62.010",
        naeringskode1_beskrivelse="IT",
        kommune="Oslo",
        broker_name="Megler",
        broker_contact="Ola",
        broker_email="o@m.no",
        broker_phone="123",
        anbefalinger=[
            {
                "type": "A",
                "prioritet": "Må ha",
                "anbefalt_sum": "1M",
                "begrunnelse": "x",
            }
        ],
        total_premie="50 000 kr",
        sammendrag="Oppsummering",
        offer_summaries=[],
    )
    assert isinstance(result, bytes)


@patch("api.services.pdf_offer.FPDF")
def test_generate_forsikringstilbud_pdf_with_offers(mock_fpdf_cls):
    mock_pdf = MagicMock()
    mock_pdf.output.return_value = b"%PDF-fake"
    mock_pdf.get_y.return_value = 50.0
    mock_fpdf_cls.return_value = mock_pdf

    result = generate_forsikringstilbud_pdf(
        orgnr="123",
        navn="X",
        organisasjonsform_kode=None,
        naeringskode1=None,
        naeringskode1_beskrivelse=None,
        kommune=None,
        broker_name="B",
        broker_contact="",
        broker_email="",
        broker_phone="",
        anbefalinger=[],
        total_premie="0",
        sammendrag="",
        offer_summaries=[
            {
                "selskap": "If",
                "premie": "1",
                "dekning": "2",
                "egenandel": "3",
                "vilkaar": "4",
                "styrker": "a",
                "svakheter": "b",
            }
        ],
    )
    assert isinstance(result, bytes)
