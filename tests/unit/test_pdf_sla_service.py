"""Tests for api/services/pdf_sla.py — SLA agreement PDF generation."""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.services.pdf_sla import (
    _add_cover_page,
    _add_section_oppdrag,
    _add_vedlegg_a,
    _add_vedlegg_b,
    _add_standardvilkar,
    _add_vedlegg_e,
    _add_signature_page,
    generate_sla_pdf,
)


def _pdf():
    m = MagicMock()
    m.get_y.return_value = 50.0
    m.l_margin = 20
    m.w = 210
    m.r_margin = 20
    return m


def _agreement(**overrides):
    defaults = dict(
        client_navn="Klient AS",
        client_orgnr="987654321",
        client_adresse="Storgata 1, 0001 Oslo",
        client_kontakt="Kari Nordmann",
        account_manager="Ola Nordmann",
        start_date="2026-01-01",
        created_at="2026-01-01T12:00:00",
        broker_snapshot={
            "firm_name": "Megler AS",
            "orgnr": "111222333",
            "address": "Meglerveien 2",
            "contact_email": "m@m.no",
            "contact_phone": "99887766",
        },
        form_data={
            "kyc_signatory": "Kari",
            "kyc_id_type": "Pass",
            "kyc_id_ref": "NO123",
            "kyc_firmadato": "2026-01-01",
            "other_lines": "Spesial",
        },
        insurance_lines=["Eiendom", "Ansvar"],
        fee_structure={
            "lines": [
                {"line": "Eiendom", "type": "provisjon", "rate": "15"},
                {"line": "Ansvar", "type": "fast", "rate": "25000"},
            ]
        },
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ── Page builder tests ───────────────────────────────────────────────────────


def test_add_cover_page():
    pdf = _pdf()
    _add_cover_page(pdf, _agreement(), {"firm_name": "Megler AS"}, "Megler AS")
    pdf.add_page.assert_called_once()
    assert pdf.cell.called


def test_add_section_oppdrag():
    pdf = _pdf()
    broker = {
        "orgnr": "111",
        "address": "Adr",
        "contact_email": "e",
        "contact_phone": "p",
    }
    _add_section_oppdrag(pdf, _agreement(), broker, "Megler AS")
    pdf.add_page.assert_called_once()
    assert pdf.multi_cell.called


def test_add_vedlegg_a():
    pdf = _pdf()
    agr = _agreement()
    _add_vedlegg_a(pdf, agr, agr.form_data, agr.insurance_lines)
    pdf.add_page.assert_called_once()
    assert pdf.cell.called


def test_add_vedlegg_a_no_other_lines():
    pdf = _pdf()
    agr = _agreement(form_data={})
    _add_vedlegg_a(pdf, agr, agr.form_data, ["Eiendom"])
    assert pdf.cell.called


def test_add_vedlegg_b_provisjon():
    pdf = _pdf()
    fees = [{"line": "Eiendom", "type": "provisjon", "rate": "15"}]
    _add_vedlegg_b(pdf, fees)
    pdf.add_page.assert_called_once()


def test_add_vedlegg_b_fast():
    pdf = _pdf()
    fees = [{"line": "Ansvar", "type": "fast", "rate": "25000"}]
    _add_vedlegg_b(pdf, fees)
    assert pdf.cell.called


def test_add_vedlegg_b_unknown_type():
    pdf = _pdf()
    fees = [{"line": "X", "type": "ukjent", "rate": ""}]
    _add_vedlegg_b(pdf, fees)
    assert pdf.cell.called


def test_add_standardvilkar():
    pdf = _pdf()
    _add_standardvilkar(pdf)
    pdf.add_page.assert_called_once()
    assert pdf.multi_cell.called


def test_add_vedlegg_e():
    pdf = _pdf()
    form = {
        "kyc_signatory": "Kari",
        "kyc_id_type": "Pass",
        "kyc_id_ref": "123",
        "kyc_firmadato": "2026-01-01",
    }
    _add_vedlegg_e(pdf, form)
    pdf.add_page.assert_called_once()
    assert pdf.multi_cell.called


def test_add_vedlegg_e_empty_form():
    pdf = _pdf()
    _add_vedlegg_e(pdf, {})
    assert pdf.multi_cell.called


def test_add_signature_page():
    pdf = _pdf()
    _add_signature_page(pdf, _agreement(), "Megler AS")
    pdf.add_page.assert_called_once()
    assert pdf.line.called


# ── Orchestrator ─────────────────────────────────────────────────────────────


@patch("api.services.pdf_sla.FPDF")
def test_generate_sla_pdf_returns_bytes(mock_fpdf_cls):
    mock_pdf = MagicMock()
    mock_pdf.output.return_value = b"%PDF-sla"
    mock_pdf.get_y.return_value = 50.0
    mock_pdf.l_margin = 20
    mock_pdf.w = 210
    mock_pdf.r_margin = 20
    mock_pdf.page_no.return_value = 1

    # generate_sla_pdf creates a _PDF subclass inside, so we need to mock FPDF
    # at the class level. The subclass calls super().__init__() which goes to our mock.
    mock_fpdf_cls.return_value = mock_pdf
    # The function creates a local _PDF(FPDF) subclass - we need to patch
    # differently. Let's just test that it doesn't crash by calling with
    # the real FPDF but mocking output.
    agr = _agreement()
    with patch("api.services.pdf_sla.FPDF") as MockFPDF:
        # Make the subclass inherit from our mock
        MockFPDF.__init_subclass__ = lambda **kw: None
        mock_instance = MagicMock()
        mock_instance.output.return_value = b"%PDF-sla"
        mock_instance.get_y.return_value = 50.0
        mock_instance.l_margin = 20
        mock_instance.w = 210
        mock_instance.r_margin = 20
        mock_instance.page_no.return_value = 1
        MockFPDF.return_value = mock_instance
        # Since generate_sla_pdf defines _PDF(FPDF) locally and FPDF is patched,
        # _PDF will inherit from our mock class. But instantiation still
        # goes through __init__ of the mock. We test the helpers above
        # individually; this test just verifies no crash + bytes returned.
        # Use the real FPDF to avoid metaclass issues.
    # Instead, test with real FPDF — the function is self-contained.
    result = generate_sla_pdf(agr)
    assert isinstance(result, bytes)
    assert len(result) > 0
