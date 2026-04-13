"""Tests for api/services/pdf_certificate.py — insurance certificate PDF generation."""
import sys
from unittest.mock import MagicMock

sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.services.pdf_certificate import (
    _fmt_nok,
    generate_certificate_pdf,
)


# ── Pure function tests ──────────────────────────────────────────────────────

def test_fmt_nok_none():
    assert _fmt_nok(None) == "–"


def test_fmt_nok_integer():
    result = _fmt_nok(100000)
    assert "100" in result
    assert "kr" in result


def test_fmt_nok_float():
    result = _fmt_nok(99999.5)
    assert "kr" in result


def test_fmt_nok_zero():
    result = _fmt_nok(0)
    assert "0" in result


def test_fmt_nok_bad_string():
    assert _fmt_nok("abc") == "abc"


# ── Orchestrator tests (real FPDF) ───────────────────────────────────────────

def test_generate_certificate_pdf_basic():
    policies = [
        {"product_type": "Eiendom", "insurer": "Gjensidige", "policy_number": "POL-001",
         "coverage_amount_nok": 5_000_000, "annual_premium_nok": 45_000, "renewal_date": "2027-01-01", "status": "active"},
    ]
    result = generate_certificate_pdf(
        orgnr="123456789", company_name="Test AS",
        policies=policies,
        broker={"firm_name": "Megler AS", "contact_name": "Ola",
                "contact_email": "ola@m.no", "contact_phone": "123"},
    )
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_generate_certificate_pdf_multiple_policies():
    policies = [
        {"product_type": "Eiendom", "insurer": "Gjensidige", "policy_number": "P1",
         "coverage_amount_nok": 5_000_000, "annual_premium_nok": 45_000, "renewal_date": "2027-01-01", "status": "active"},
        {"product_type": "Ansvar", "insurer": "If", "policy_number": "P2",
         "coverage_amount_nok": 10_000_000, "annual_premium_nok": 30_000, "renewal_date": "2027-06-01", "status": "active"},
        {"product_type": "Reise", "insurer": "Tryg", "policy_number": "",
         "coverage_amount_nok": None, "annual_premium_nok": None, "renewal_date": "", "status": "active"},
    ]
    result = generate_certificate_pdf(
        orgnr="987654321", company_name="Stor AS",
        policies=policies, broker={"firm_name": "M"},
    )
    assert isinstance(result, bytes)


def test_generate_certificate_pdf_no_active_policies():
    policies = [
        {"product_type": "Eiendom", "insurer": "X", "status": "cancelled"},
    ]
    result = generate_certificate_pdf(
        orgnr="111", company_name="Tom AS",
        policies=policies, broker={"firm_name": "M"},
    )
    assert isinstance(result, bytes)


def test_generate_certificate_pdf_empty_policies():
    result = generate_certificate_pdf(
        orgnr="222", company_name="Ingen AS",
        policies=[], broker={"firm_name": "M"},
    )
    assert isinstance(result, bytes)


def test_generate_certificate_pdf_mixed_status():
    policies = [
        {"product_type": "A", "insurer": "X", "policy_number": "1",
         "coverage_amount_nok": 1000, "annual_premium_nok": 100, "renewal_date": "2027-01-01", "status": "active"},
        {"product_type": "B", "insurer": "Y", "status": "expired"},
        {"product_type": "C", "insurer": "Z", "policy_number": "3",
         "coverage_amount_nok": 3000, "annual_premium_nok": 300, "renewal_date": "2027-03-01", "status": "active"},
    ]
    result = generate_certificate_pdf(
        orgnr="333", company_name="Mix AS",
        policies=policies, broker={"firm_name": "M"},
    )
    assert isinstance(result, bytes)


def test_generate_certificate_pdf_empty_broker():
    policies = [
        {"product_type": "P", "insurer": "I", "policy_number": "N",
         "coverage_amount_nok": 500, "annual_premium_nok": 50, "renewal_date": "2027-01-01", "status": "active"},
    ]
    result = generate_certificate_pdf(
        orgnr="444", company_name="Minimal AS",
        policies=policies, broker={},
    )
    assert isinstance(result, bytes)


def test_generate_certificate_pdf_long_values_truncated():
    """Ensure long values don't crash (they get truncated to 22 chars)."""
    policies = [
        {"product_type": "A" * 50, "insurer": "B" * 50, "policy_number": "C" * 50,
         "coverage_amount_nok": 99_999_999, "annual_premium_nok": 88_888_888,
         "renewal_date": "2027-12-31", "status": "active"},
    ]
    result = generate_certificate_pdf(
        orgnr="555", company_name="Lang AS",
        policies=policies, broker={"firm_name": "M"},
    )
    assert isinstance(result, bytes)
