"""Unit tests for api/services/recommendation_service.py — mocked DB and LLM."""

import sys
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

import pytest

sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.services.recommendation_service import (
    _build_rationale_prompt,
    RecommendationService,
)
from api.domain.exceptions import NotFoundError


# ── _build_rationale_prompt ──────────────────────────────────────────────────


def test_build_prompt_includes_company_and_insurer():
    prompt = _build_rationale_prompt("DNB ASA", "984851006", "Gjensidige", [], None)
    assert "DNB ASA" in prompt
    assert "Gjensidige" in prompt
    assert "984851006" in prompt


def test_build_prompt_includes_idd_when_provided():
    idd = SimpleNamespace(
        risk_appetite="medium", recommended_products=["Ansvar", "Eiendom"]
    )
    prompt = _build_rationale_prompt("Test AS", "123", "If", [], idd)
    assert "medium" in prompt
    assert "Ansvar" in prompt


def test_build_prompt_includes_submissions():
    sub = SimpleNamespace(
        product_type="Ansvar",
        status="quoted",
        premium_offered_nok=50_000,
        notes="God dekning",
    )
    prompt = _build_rationale_prompt("Test AS", "123", "If", [sub], None)
    assert "50,000 kr" in prompt or "50 000 kr" in prompt
    assert "Tilbud mottatt" in prompt


def test_build_prompt_handles_no_premium():
    sub = SimpleNamespace(
        product_type="Eiendom",
        status="pending",
        premium_offered_nok=None,
        notes=None,
    )
    prompt = _build_rationale_prompt("Test AS", "123", "If", [sub], None)
    assert "ikke oppgitt" in prompt


# ── RecommendationService ────────────────────────────────────────────────────


def _make_db():
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    db.query.return_value.filter.return_value.all.return_value = []
    db.query.return_value.filter.return_value.first.return_value = None
    return db


def test_list_returns_empty():
    db = _make_db()
    svc = RecommendationService(db)
    result = svc.list("123456789", firm_id=1)
    assert result == []


def test_create_with_rationale_override():
    db = _make_db()
    svc = RecommendationService(db)
    svc.create(
        orgnr="123",
        firm_id=1,
        created_by_email="a@b.com",
        company_name="Test AS",
        recommended_insurer="Gjensidige",
        submission_ids=None,
        idd_id=None,
        rationale_override="Manual rationale text",
    )
    db.add.assert_called_once()
    db.commit.assert_called_once()
    added_row = db.add.call_args[0][0]
    assert added_row.rationale_text == "Manual rationale text"


def test_create_calls_llm_when_no_override():
    db = _make_db()
    svc = RecommendationService(db)
    with patch(
        "api.services.recommendation_service._llm_answer_raw",
        return_value="LLM says this",
    ):
        svc.create(
            orgnr="123",
            firm_id=1,
            created_by_email="a@b.com",
            company_name="Test AS",
            recommended_insurer="If",
            submission_ids=None,
            idd_id=None,
            rationale_override=None,
        )
    added_row = db.add.call_args[0][0]
    assert added_row.rationale_text == "LLM says this"


def test_create_uses_fallback_when_llm_returns_none():
    db = _make_db()
    svc = RecommendationService(db)
    with patch(
        "api.services.recommendation_service._llm_answer_raw", return_value=None
    ):
        svc.create(
            orgnr="123",
            firm_id=1,
            created_by_email="a@b.com",
            company_name="Test AS",
            recommended_insurer="If",
            submission_ids=None,
            idd_id=None,
            rationale_override=None,
        )
    added_row = db.add.call_args[0][0]
    assert "If" in added_row.rationale_text
    assert "anbefales" in added_row.rationale_text


def test_get_raises_not_found():
    db = _make_db()
    svc = RecommendationService(db)
    with pytest.raises(NotFoundError, match="not found"):
        svc.get("123", firm_id=1, rec_id=999)


def test_delete_raises_not_found():
    db = _make_db()
    svc = RecommendationService(db)
    with pytest.raises(NotFoundError):
        svc.delete("123", firm_id=1, rec_id=999)


def test_store_pdf_updates_row():
    row = MagicMock()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = row
    svc = RecommendationService(db)
    svc.store_pdf(rec_id=1, pdf_bytes=b"%PDF-1.4")
    assert row.pdf_content == b"%PDF-1.4"
    db.commit.assert_called_once()


def test_mark_signed_by_session_updates_row():
    row = MagicMock(signing_session_id="sess-123")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = row
    svc = RecommendationService(db)
    result = svc.mark_signed_by_session(
        "sess-123", signed_pdf_blob_url="https://blob/signed.pdf"
    )
    assert result is row
    assert row.signed_pdf_blob_url == "https://blob/signed.pdf"
    db.commit.assert_called_once()


def test_mark_signed_returns_none_for_unknown_session():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    svc = RecommendationService(db)
    result = svc.mark_signed_by_session("unknown-session")
    assert result is None
