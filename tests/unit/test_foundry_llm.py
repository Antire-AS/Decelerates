"""Unit tests for api/adapters/foundry_llm_adapter.py — Foundry chat + embed.

Tests FoundryLlmAdapter directly with mocked OpenAI client and HTTP calls.
No real Azure AI Foundry or network required.
"""

import sys
from unittest.mock import MagicMock, patch


# Stub heavy transitive deps before any api.* import
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.adapters.foundry_llm_adapter import (
    FoundryConfig,
    FoundryLlmAdapter,
    _derive_azure_host,
)


# -- is_configured / embeddings_configured ------------------------------------


def test_is_configured_true_when_both_set():
    cfg = FoundryConfig(
        base_url="https://host/api/projects/p/openai/v1", api_key="real-key"
    )
    assert FoundryLlmAdapter(cfg).is_configured() is True


def test_is_configured_false_when_no_key():
    cfg = FoundryConfig(base_url="https://host/api/projects/p/openai/v1", api_key=None)
    assert FoundryLlmAdapter(cfg).is_configured() is False


def test_is_configured_false_when_placeholder_key():
    cfg = FoundryConfig(base_url="https://host/path", api_key="your_key_here")
    assert FoundryLlmAdapter(cfg).is_configured() is False


def test_embeddings_configured_requires_deployment():
    cfg = FoundryConfig(base_url="https://h/p", api_key="key", embedding_deployment="")
    assert FoundryLlmAdapter(cfg).embeddings_configured() is False


# -- _derive_azure_host --------------------------------------------------------


def test_derive_azure_host_strips_path():
    assert (
        _derive_azure_host("https://my-host.openai.azure.com/api/proj/openai/v1")
        == "https://my-host.openai.azure.com"
    )


# -- chat() --------------------------------------------------------------------


def test_chat_returns_none_when_not_configured():
    cfg = FoundryConfig(base_url=None, api_key=None)
    assert FoundryLlmAdapter(cfg).chat("hello") is None


@patch("api.adapters.foundry_llm_adapter.OpenAI", create=True)
def test_chat_success(mock_openai_cls):
    mock_client = MagicMock()
    choice = MagicMock()
    choice.message.content = "response text"
    mock_client.chat.completions.create.return_value = MagicMock(choices=[choice])

    cfg = FoundryConfig(base_url="https://host/v1", api_key="key")
    adapter = FoundryLlmAdapter(cfg)
    adapter._chat_client = mock_client

    result = adapter.chat("hello", system_prompt="be helpful")
    assert result == "response text"
    mock_client.chat.completions.create.assert_called_once()


@patch("api.adapters.foundry_llm_adapter.OpenAI", create=True)
def test_chat_returns_none_on_exception(mock_openai_cls):
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("timeout")

    cfg = FoundryConfig(base_url="https://host/v1", api_key="key")
    adapter = FoundryLlmAdapter(cfg)
    adapter._chat_client = mock_client

    assert adapter.chat("hello") is None


# -- embed() -------------------------------------------------------------------


@patch("api.adapters.foundry_llm_adapter.requests")
def test_embed_success(mock_requests):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3]}]}
    mock_resp.raise_for_status = MagicMock()
    mock_requests.post.return_value = mock_resp

    cfg = FoundryConfig(
        base_url="https://host.com/api/projects/p/openai/v1", api_key="key"
    )
    result = FoundryLlmAdapter(cfg).embed("test text")
    assert result == [0.1, 0.2, 0.3]
    mock_requests.post.assert_called_once()


@patch("api.adapters.foundry_llm_adapter.requests")
def test_embed_returns_none_on_error(mock_requests):
    mock_requests.post.side_effect = ConnectionError("no network")
    cfg = FoundryConfig(
        base_url="https://host.com/api/projects/p/openai/v1", api_key="key"
    )
    assert FoundryLlmAdapter(cfg).embed("text") is None


def test_embed_returns_none_when_not_configured():
    cfg = FoundryConfig(base_url=None, api_key=None)
    assert FoundryLlmAdapter(cfg).embed("text") is None
