"""Expanded unit tests for api/services/llm.py — LLM answer + compare + embed."""

import sys
from unittest.mock import MagicMock, patch

sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.services.llm import (
    _llm_answer_raw,
    _llm_answer,
    _compare_offers_with_llm,
    _fmt_nok,
)
from api.domain.exceptions import LlmUnavailableError


# ── _fmt_nok ──────────────────────────────────────────────────────────────────


def test_fmt_nok_millions():
    assert "MNOK" in _fmt_nok(50_000_000)


def test_fmt_nok_none():
    assert _fmt_nok(None) == "–" or _fmt_nok(None) == "-"


def test_fmt_nok_zero():
    assert "0" in str(_fmt_nok(0))


# ── _llm_answer_raw ──────────────────────────────────────────────────────────


@patch("api.services.llm._try_foundry_chat", return_value="Generated text")
def test_llm_answer_raw_success(mock_chat):
    result = _llm_answer_raw("prompt")
    assert result == "Generated text"


@patch("api.services.llm._try_foundry_chat", return_value=None)
def test_llm_answer_raw_no_provider(mock_chat):
    result = _llm_answer_raw("prompt")
    assert result is None


# ── _llm_answer ───────────────────────────────────────────────────────────────


@patch("api.services.llm._try_foundry_chat", return_value="Answer about company")
def test_llm_answer_success(mock_chat):
    result = _llm_answer("Context: revenue 100M", "What is the revenue?")
    assert result == "Answer about company"


@patch("api.services.llm._try_foundry_chat", return_value=None)
def test_llm_answer_raises_when_unconfigured(mock_chat):
    import pytest

    with pytest.raises(LlmUnavailableError):
        _llm_answer("ctx", "q")


# ── _compare_offers_with_llm ─────────────────────────────────────────────────


@patch("api.services.llm._try_foundry_chat", return_value="Comparison result")
def test_compare_offers_success(mock_chat):
    result = _compare_offers_with_llm("Compare offer A vs B")
    assert result == "Comparison result"


@patch("api.services.llm._try_foundry_chat", return_value=None)
def test_compare_offers_returns_none(mock_chat):
    assert _compare_offers_with_llm("prompt") is None
