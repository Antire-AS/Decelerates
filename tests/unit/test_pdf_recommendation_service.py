"""Tests for api/services/pdf_recommendation.py — recommendation letter PDF generation."""
import sys
from unittest.mock import MagicMock

sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.services.pdf_recommendation import (
    _fmt_nok,
    generate_recommendation_pdf,
)


# ── Pure function tests ──────────────────────────────────────────────────────

def test_fmt_nok_none():
    assert _fmt_nok(None) == "–"


def test_fmt_nok_integer():
    result = _fmt_nok(50000)
    assert "50" in result
    assert "kr" in result


def test_fmt_nok_float():
    result = _fmt_nok(123456.78)
    assert "123" in result
    assert "kr" in result


def test_fmt_nok_zero():
    result = _fmt_nok(0)
    assert "0" in result
    assert "kr" in result


def test_fmt_nok_string():
    result = _fmt_nok("not a number")
    assert result == "not a number"


def test_fmt_nok_numeric_string():
    result = _fmt_nok("25000")
    assert "25" in result
    assert "kr" in result


# ── Orchestrator tests (real FPDF) ───────────────────────────────────────────

def test_generate_recommendation_pdf_basic():
    result = generate_recommendation_pdf(
        orgnr="123456789",
        company_name="Test AS",
        recommended_insurer="Gjensidige",
        rationale_text="Beste pris og dekning.\n\nGod service.",
        submissions=[],
        broker={"firm_name": "Megler AS", "contact_name": "Ola",
                "contact_email": "ola@m.no", "contact_phone": "123"},
    )
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_generate_recommendation_pdf_with_submissions():
    submissions = [
        {"insurer_name": "Gjensidige", "product_type": "Eiendom",
         "premium_offered_nok": 45000, "status": "quoted", "requested_at": "2026-01-10"},
        {"insurer_name": "If", "product_type": "Eiendom",
         "premium_offered_nok": 52000, "status": "quoted", "requested_at": "2026-01-11"},
        {"insurer_name": "Tryg", "product_type": "Eiendom",
         "premium_offered_nok": None, "status": "declined", "requested_at": "2026-01-09"},
    ]
    result = generate_recommendation_pdf(
        orgnr="987654321",
        company_name="Stor Bedrift AS",
        recommended_insurer="Gjensidige",
        rationale_text="Lavest premie med bred dekning.",
        submissions=submissions,
        broker={"firm_name": "Megler AS", "contact_name": "Kari"},
    )
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_generate_recommendation_pdf_no_rationale():
    result = generate_recommendation_pdf(
        orgnr="111",
        company_name="Mini AS",
        recommended_insurer="If",
        rationale_text="",
        submissions=[],
        broker={"firm_name": "M"},
    )
    assert isinstance(result, bytes)


def test_generate_recommendation_pdf_with_created_by():
    result = generate_recommendation_pdf(
        orgnr="222",
        company_name="X AS",
        recommended_insurer="Tryg",
        rationale_text="Grunn.",
        submissions=[],
        broker={"firm_name": "M", "contact_name": ""},
        created_by_email="bruker@firma.no",
    )
    assert isinstance(result, bytes)


def test_generate_recommendation_pdf_empty_broker():
    result = generate_recommendation_pdf(
        orgnr="333",
        company_name="Y AS",
        recommended_insurer="Storebrand",
        rationale_text="OK tilbud.",
        submissions=[],
        broker={},
    )
    assert isinstance(result, bytes)


def test_generate_recommendation_pdf_submission_statuses():
    """Cover all status_no mappings."""
    submissions = [
        {"insurer_name": "A", "product_type": "P", "premium_offered_nok": 1000, "status": "pending", "requested_at": ""},
        {"insurer_name": "B", "product_type": "P", "premium_offered_nok": 2000, "status": "withdrawn", "requested_at": None},
        {"insurer_name": "C", "product_type": "P", "premium_offered_nok": None, "status": "unknown_status", "requested_at": "2026-01-01"},
    ]
    result = generate_recommendation_pdf(
        orgnr="444", company_name="Z AS", recommended_insurer="A",
        rationale_text="Test.", submissions=submissions, broker={"firm_name": "M"},
    )
    assert isinstance(result, bytes)
