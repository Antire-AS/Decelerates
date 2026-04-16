"""Unit tests for api/services/pdf_generate.py — PdfGenerateService class wrapper."""
import sys
from unittest.mock import MagicMock, patch

sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

import pytest


class TestPdfGenerateServiceGenerateSla:
    def test_delegates_to_module_function(self):
        with patch("api.services.pdf_generate._generate_sla_pdf", return_value=b"%PDF-sla") as mock_fn:
            from api.services.pdf_generate import PdfGenerateService
            svc = PdfGenerateService()
            agreement = MagicMock()
            result = svc.generate_sla(agreement)
        assert result == b"%PDF-sla"
        mock_fn.assert_called_once_with(agreement)


class TestPdfGenerateServiceGenerateRiskReport:
    def test_delegates_to_module_function(self):
        with patch("api.services.pdf_generate.generate_risk_report_pdf", return_value=b"%PDF-risk") as mock_fn:
            from api.services.pdf_generate import PdfGenerateService
            svc = PdfGenerateService()
            result = svc.generate_risk_report(org={"navn": "Test"}, score=5)
        assert result == b"%PDF-risk"
        mock_fn.assert_called_once_with(org={"navn": "Test"}, score=5)


class TestPdfGenerateServiceGenerateForsikringstilbud:
    def test_delegates_to_module_function(self):
        with patch("api.services.pdf_generate.generate_forsikringstilbud_pdf", return_value=b"%PDF-tilbud") as mock_fn:
            from api.services.pdf_generate import PdfGenerateService
            svc = PdfGenerateService()
            result = svc.generate_forsikringstilbud(navn="Acme", orgnr="123")
        assert result == b"%PDF-tilbud"
        mock_fn.assert_called_once_with(navn="Acme", orgnr="123")


class TestPdfGenerateServiceGeneratePortfolio:
    def test_delegates_to_module_function(self):
        with patch("api.services.pdf_generate.generate_portfolio_pdf", return_value=b"%PDF-port") as mock_fn:
            from api.services.pdf_generate import PdfGenerateService
            svc = PdfGenerateService()
            result = svc.generate_portfolio(name="My Portfolio")
        assert result == b"%PDF-port"
        mock_fn.assert_called_once_with(name="My Portfolio")


class TestPdfGenerateReExports:
    """Verify that the backward-compat shim re-exports expected symbols."""

    def test_safe_is_reexported(self):
        from api.services.pdf_generate import _safe
        assert callable(_safe)

    def test_section_title_is_reexported(self):
        from api.services.pdf_generate import _section_title
        assert callable(_section_title)

    def test_dark_blue_constant(self):
        from api.services.pdf_generate import _DARK_BLUE
        assert isinstance(_DARK_BLUE, tuple)
        assert len(_DARK_BLUE) == 3

    def test_light_blue_constant(self):
        from api.services.pdf_generate import _LIGHT_BLUE
        assert isinstance(_LIGHT_BLUE, tuple)
        assert len(_LIGHT_BLUE) == 3

    def test_extract_offer_summary_is_reexported(self):
        from api.services.pdf_generate import _extract_offer_summary
        assert callable(_extract_offer_summary)

    def test_generate_risk_report_pdf_is_reexported(self):
        from api.services.pdf_generate import generate_risk_report_pdf
        assert callable(generate_risk_report_pdf)
