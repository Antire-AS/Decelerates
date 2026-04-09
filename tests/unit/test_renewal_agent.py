"""Unit tests for api/services/renewal_agent.py.

Mocks the DB query chain + LLM call. Verifies prompt construction and the
empty/missing-data fallbacks.
"""
from datetime import date
from unittest.mock import MagicMock, patch

from api.services.renewal_agent import (
    RenewalAgentService,
    _get_gap_summary,
    _get_submission_context,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _mock_policy(
    orgnr="123456789",
    firm_id=1,
    product_type="Bedriftsansvar",
    insurer="If",
    renewal_date=date(2026, 6, 1),
    annual_premium_nok=125000,
):
    p = MagicMock()
    p.orgnr = orgnr
    p.firm_id = firm_id
    p.product_type = product_type
    p.insurer = insurer
    p.renewal_date = renewal_date
    p.annual_premium_nok = annual_premium_nok
    return p


def _mock_query_chain(return_value, kind="all"):
    chain = MagicMock()
    chain.filter.return_value = chain
    chain.order_by.return_value = chain
    chain.limit.return_value = chain
    if kind == "all":
        chain.all.return_value = return_value
    elif kind == "first":
        chain.first.return_value = return_value
    return chain


# ── _get_gap_summary ──────────────────────────────────────────────────────────

def test_get_gap_summary_returns_norwegian_summary_when_gaps_exist():
    db = MagicMock()
    policy = _mock_policy()
    fake_gap = {
        "gap_count": 2,
        "items": [
            {"type": "Cyber", "status": "gap"},
            {"type": "D&O", "status": "gap"},
            {"type": "Bedriftsansvar", "status": "covered"},
        ],
    }
    with patch("api.services.coverage_gap.analyze_coverage_gap", return_value=fake_gap):
        result = _get_gap_summary(policy, db)
    assert "Manglende dekning" in result
    assert "Cyber" in result
    assert "D&O" in result
    assert "Bedriftsansvar" not in result  # covered, should be excluded


def test_get_gap_summary_returns_empty_when_no_gaps():
    db = MagicMock()
    policy = _mock_policy()
    with patch(
        "api.services.coverage_gap.analyze_coverage_gap",
        return_value={"gap_count": 0, "items": []},
    ):
        result = _get_gap_summary(policy, db)
    assert result == ""


def test_get_gap_summary_swallows_analyzer_exceptions():
    db = MagicMock()
    policy = _mock_policy()
    with patch(
        "api.services.coverage_gap.analyze_coverage_gap",
        side_effect=RuntimeError("analyzer broken"),
    ):
        result = _get_gap_summary(policy, db)
    assert result == ""


# ── _get_submission_context ───────────────────────────────────────────────────

def test_get_submission_context_returns_empty_when_no_submissions():
    db = MagicMock()
    db.query.return_value = _mock_query_chain([], kind="all")
    result = _get_submission_context(_mock_policy(), db)
    assert result == ""


def test_get_submission_context_formats_submission_lines():
    db = MagicMock()
    sub1 = MagicMock()
    sub1.status = MagicMock(value="quoted")
    sub1.premium_offered_nok = 95000
    sub2 = MagicMock()
    sub2.status = MagicMock(value="declined")
    sub2.premium_offered_nok = None
    db.query.return_value = _mock_query_chain([sub1, sub2], kind="all")

    result = _get_submission_context(_mock_policy(), db)

    assert "Tidligere markedstilnærminger" in result
    assert "quoted" in result
    assert "95,000 NOK" in result
    assert "declined" in result
    assert "ikke oppgitt" in result


def test_get_submission_context_handles_null_status():
    db = MagicMock()
    sub = MagicMock()
    sub.status = None
    sub.premium_offered_nok = 50000
    db.query.return_value = _mock_query_chain([sub], kind="all")

    result = _get_submission_context(_mock_policy(), db)
    assert "ukjent" in result


# ── RenewalAgentService.generate_renewal_brief ────────────────────────────────

def test_generate_renewal_brief_returns_llm_output():
    db = MagicMock()
    company = MagicMock()
    company.navn = "DNB BANK ASA"
    db.query.return_value = _mock_query_chain(company, kind="first")
    policy = _mock_policy(orgnr="984851006", insurer="Tryg")

    fake_llm_output = "- aksjon 1\n- aksjon 2\n- aksjon 3"
    with patch("api.services.llm._llm_answer_raw", return_value=fake_llm_output), \
         patch("api.services.coverage_gap.analyze_coverage_gap", return_value={"gap_count": 0, "items": []}):
        result = RenewalAgentService().generate_renewal_brief(policy, db)
    assert result == fake_llm_output


def test_generate_renewal_brief_returns_empty_string_when_llm_returns_none():
    db = MagicMock()
    company = MagicMock()
    company.navn = "Test Company"
    db.query.return_value = _mock_query_chain(company, kind="first")
    policy = _mock_policy()

    with patch("api.services.llm._llm_answer_raw", return_value=None), \
         patch("api.services.coverage_gap.analyze_coverage_gap", return_value={"gap_count": 0, "items": []}):
        result = RenewalAgentService().generate_renewal_brief(policy, db)
    assert result == ""


def test_generate_renewal_brief_uses_orgnr_when_company_missing():
    db = MagicMock()
    db.query.return_value = _mock_query_chain(None, kind="first")
    policy = _mock_policy(orgnr="999888777")

    captured_prompt = {}
    def capture_prompt(prompt):
        captured_prompt["text"] = prompt
        return "ok"

    with patch("api.services.llm._llm_answer_raw", side_effect=capture_prompt), \
         patch("api.services.coverage_gap.analyze_coverage_gap", return_value={"gap_count": 0, "items": []}):
        RenewalAgentService().generate_renewal_brief(policy, db)

    # Falls back to orgnr as the customer name when no Company row exists.
    assert "999888777" in captured_prompt["text"]


def test_generate_renewal_brief_handles_null_renewal_date_and_premium():
    db = MagicMock()
    db.query.return_value = _mock_query_chain(None, kind="first")
    policy = _mock_policy(renewal_date=None, annual_premium_nok=None)

    captured = {}
    with patch("api.services.llm._llm_answer_raw", side_effect=lambda p: captured.update(text=p) or "ok"), \
         patch("api.services.coverage_gap.analyze_coverage_gap", return_value={"gap_count": 0, "items": []}):
        RenewalAgentService().generate_renewal_brief(policy, db)

    assert "ukjent" in captured["text"]
    assert "ikke oppgitt" in captured["text"]
