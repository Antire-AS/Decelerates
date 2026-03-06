"""Unit tests for services/llm.py — all external calls are mocked."""
import os
from unittest.mock import MagicMock, patch

import pytest

from domain.exceptions import LlmUnavailableError, QuotaError


# ── _embed ────────────────────────────────────────────────────────────────────

def test_embed_voyage_success(monkeypatch):
    monkeypatch.setenv("VOYAGE_API_KEY", "test-voyage-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    mock_result = MagicMock()
    mock_result.embeddings = [[0.1, 0.2, 0.3]]

    with patch("voyageai.Client") as mock_client_cls:
        mock_client_cls.return_value.embed.return_value = mock_result
        from services.llm import _embed
        result = _embed("hello world")

    assert result == [0.1, 0.2, 0.3]


def test_embed_gemini_fallback(monkeypatch):
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    mock_embedding = MagicMock()
    mock_embedding.values = [0.4, 0.5]
    mock_result = MagicMock()
    mock_result.embeddings = [mock_embedding]

    with patch("google.genai.Client") as mock_client_cls:
        mock_client_cls.return_value.models.embed_content.return_value = mock_result
        from services.llm import _embed
        result = _embed("hello world")

    assert result == [0.4, 0.5]


def test_embed_no_keys_returns_empty(monkeypatch):
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    from services.llm import _embed
    result = _embed("hello world")
    assert result == []


# ── _llm_answer_raw ───────────────────────────────────────────────────────────

def test_llm_answer_raw_claude(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-claude-key")

    mock_content = MagicMock()
    mock_content.text = "The answer is 42."
    mock_msg = MagicMock()
    mock_msg.content = [mock_content]

    with patch("anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.return_value = mock_msg
        from services.llm import _llm_answer_raw
        result = _llm_answer_raw("What is the answer?")

    assert result == "The answer is 42."


def test_llm_answer_raw_raises_quota_error(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    quota_exc = Exception("RESOURCE_EXHAUSTED: quota exceeded")

    with patch("google.genai.Client") as mock_cls:
        mock_cls.return_value.models.generate_content.side_effect = quota_exc
        from services.llm import _llm_answer_raw
        with pytest.raises(QuotaError):
            _llm_answer_raw("What is the answer?")


def test_llm_answer_raises_lm_unavailable(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    from services.llm import _llm_answer
    with pytest.raises(LlmUnavailableError):
        _llm_answer("some context", "some question")
