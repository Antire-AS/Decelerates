"""Unit tests for api/services/coverage_service.py — AI coverage analysis."""

import sys
from unittest.mock import MagicMock, patch

import pytest

sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.services.coverage_service import (
    CoverageService,
    _extract_text,
    _safe_float,
    _analyse_with_ai,
)


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def svc(db):
    return CoverageService(db)


class TestCreateAnalysis:
    @patch(
        "api.services.coverage_service._extract_text", return_value="Dekning: ansvar"
    )
    def test_creates_pending_analysis(self, mock_extract, svc, db):
        db.commit = MagicMock()
        db.refresh = MagicMock()

        svc.create_analysis(
            orgnr="984851006",
            firm_id=1,
            title="Ansvarsforsikring",
            pdf_bytes=b"%PDF-test",
            filename="polise.pdf",
            insurer="If",
        )
        db.add.assert_called_once()
        db.commit.assert_called_once()


class TestRunAnalysis:
    def test_returns_error_for_missing(self, svc, db):
        db.query.return_value.get.return_value = None
        with pytest.raises(ValueError, match="not found"):
            svc.run_analysis(999)

    @patch("api.services.coverage_service._analyse_with_ai")
    def test_sets_status_analysed_on_success(self, mock_ai, svc, db):
        analysis = MagicMock()
        analysis.id = 1
        analysis.pdf_content = b"%PDF-test"
        analysis.extracted_text = "test"
        analysis.insurer = None
        analysis.product_type = None
        db.query.return_value.get.return_value = analysis

        mock_ai.return_value = {
            "forsikringstype": "Ansvar",
            "forsikringsgiver": "If",
            "premie_nok": 50000,
            "egenandel_nok": 10000,
            "forsikringssum_nok": 5000000,
        }

        svc.run_analysis(1)
        assert analysis.status == "analysed"
        assert analysis.premium_nok == 50000
        assert analysis.insurer == "If"
        db.commit.assert_called()

    @patch("api.services.coverage_service._analyse_with_ai")
    def test_sets_status_error_on_failure(self, mock_ai, svc, db):
        analysis = MagicMock()
        analysis.id = 1
        analysis.pdf_content = b"%PDF-test"
        analysis.extracted_text = "test"
        db.query.return_value.get.return_value = analysis

        mock_ai.return_value = None

        svc.run_analysis(1)
        assert analysis.status == "error"


class TestListForCompany:
    def test_filters_by_orgnr_and_firm_id(self, svc, db):
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        svc.list_for_company("984851006", firm_id=1)
        mock_query.filter.assert_called_once()


class TestGet:
    def test_filters_by_id_and_firm_id(self, svc, db):
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        result = svc.get(42, firm_id=1)
        assert result is None
        mock_query.filter.assert_called_once()


class TestDelete:
    def test_delete_returns_false_for_missing(self, svc, db):
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        assert svc.delete(999, firm_id=1) is False

    def test_delete_removes_and_commits(self, svc, db):
        row = MagicMock()
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = row

        assert svc.delete(1, firm_id=1) is True
        db.delete.assert_called_once_with(row)
        db.commit.assert_called_once()


class TestSafeFloat:
    def test_valid_number(self):
        assert _safe_float(42) == 42.0

    def test_string_number(self):
        assert _safe_float("123.45") == 123.45

    def test_none(self):
        assert _safe_float(None) is None

    def test_invalid(self):
        assert _safe_float("not a number") is None


class TestExtractText:
    @patch("api.services.coverage_service.pdfplumber")
    def test_returns_text(self, mock_pdfplumber):
        page = MagicMock()
        page.extract_text.return_value = "Sample policy text"
        mock_pdf = MagicMock()
        mock_pdf.pages = [page]
        mock_pdfplumber.open.return_value.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

        result = _extract_text(b"%PDF-test")
        assert result == "Sample policy text"

    @patch("api.services.coverage_service.pdfplumber")
    def test_returns_none_on_error(self, mock_pdfplumber):
        mock_pdfplumber.open.side_effect = Exception("bad pdf")
        result = _extract_text(b"not-a-pdf")
        assert result is None


class TestAnalyseWithAI:
    @patch("api.services.llm._try_foundry_chat", return_value=None)
    @patch("api.services.llm._analyze_document_with_gemini", return_value=None)
    @patch("api.services.llm._parse_json_from_llm_response", return_value=None)
    def test_returns_none_when_all_fail(self, mock_parse, mock_gemini, mock_foundry):
        result = _analyse_with_ai(b"pdf", "text")
        assert result is None

    @patch("api.services.llm._parse_json_from_llm_response")
    @patch("api.services.llm._analyze_document_with_gemini")
    def test_uses_gemini_first(self, mock_gemini, mock_parse):
        mock_gemini.return_value = '{"forsikringstype": "Ansvar"}'
        mock_parse.return_value = {"forsikringstype": "Ansvar"}

        result = _analyse_with_ai(b"pdf", "text")
        assert result == {"forsikringstype": "Ansvar"}
        mock_gemini.assert_called_once()
