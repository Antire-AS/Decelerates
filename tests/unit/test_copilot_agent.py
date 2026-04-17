"""Unit tests for api/services/copilot_agent.py — multi-turn tool-use loop."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch


from api.services.copilot_agent import (
    _build_context_message,
    _init_messages,
    _get_llm_client,
    chat_with_tools,
    COPILOT_SYSTEM_PROMPT,
)


# ── _build_context_message ────────────────────────────────────────────────────


def test_build_context_with_company():
    db = MagicMock()
    company = SimpleNamespace(
        navn="DNB BANK ASA",
        risk_score=9,
        sum_driftsinntekter=86_000_000_000,
        naeringskode1_beskrivelse="Banker",
    )
    db.query.return_value.filter.return_value.first.return_value = company
    msg = _build_context_message("984851006", db)
    assert "DNB BANK ASA" in msg
    assert "9/20" in msg
    assert "Banker" in msg


def test_build_context_no_company():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    msg = _build_context_message("000", db)
    assert "000" in msg
    assert "ikke funnet" in msg


def test_build_context_minimal_company():
    db = MagicMock()
    company = SimpleNamespace(
        navn="Minimal AS",
        risk_score=None,
        sum_driftsinntekter=None,
        naeringskode1_beskrivelse=None,
    )
    db.query.return_value.filter.return_value.first.return_value = company
    msg = _build_context_message("123", db)
    assert "Minimal AS" in msg
    assert "Risikoscore" not in msg  # None → omitted


# ── _init_messages ────────────────────────────────────────────────────────────


def test_init_messages_basic():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    msgs = _init_messages("Hva er risikoen?", "123", db, None)
    assert msgs[0]["role"] == "system"
    assert COPILOT_SYSTEM_PROMPT in msgs[0]["content"]
    assert msgs[-1]["role"] == "user"
    assert msgs[-1]["content"] == "Hva er risikoen?"


def test_init_messages_with_history():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    history = [
        {"role": "user", "content": "Hei"},
        {"role": "assistant", "content": "Hei!"},
    ]
    msgs = _init_messages("Neste spørsmål", "123", db, history)
    assert len(msgs) == 4  # system + 2 history + user


# ── _get_llm_client ───────────────────────────────────────────────────────────


@patch("api.container.resolve")
def test_get_llm_client_unconfigured(mock_resolve):
    llm = MagicMock()
    llm.is_configured.return_value = False
    mock_resolve.return_value = llm
    client, model = _get_llm_client()
    assert client is None
    assert model is None


@patch("api.container.resolve")
def test_get_llm_client_configured(mock_resolve):
    llm = MagicMock()
    llm.is_configured.return_value = True
    llm._get_chat_client.return_value = "client"
    llm._config.default_text_model = "gpt-5.4-mini"
    mock_resolve.return_value = llm
    client, model = _get_llm_client()
    assert client == "client"
    assert model == "gpt-5.4-mini"


# ── chat_with_tools ───────────────────────────────────────────────────────────


@patch("api.services.copilot_agent._get_llm_client", return_value=(None, None))
def test_chat_unconfigured_returns_error(mock_client):
    db = MagicMock()
    result = chat_with_tools("hei", "123", 1, db)
    assert "ikke konfigurert" in result["answer"]
    assert result["tool_calls_made"] == []


@patch("api.services.copilot_agent._get_llm_client")
def test_chat_no_tool_calls_returns_text(mock_client):
    client = MagicMock()
    choice = MagicMock()
    choice.message.tool_calls = None
    choice.message.content = "Her er svaret."
    client.chat.completions.create.return_value = MagicMock(choices=[choice])
    mock_client.return_value = (client, "model")

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    result = chat_with_tools("spørsmål", "123", 1, db)
    assert result["answer"] == "Her er svaret."
    assert result["tool_calls_made"] == []


@patch("api.services.copilot_agent.execute_tool", return_value="Verktøy-resultat")
@patch("api.services.copilot_agent._get_llm_client")
def test_chat_with_one_tool_call(mock_client, mock_exec):
    client = MagicMock()
    # First call: tool_call response
    tc = MagicMock()
    tc.function.name = "run_coverage_gap"
    tc.function.arguments = "{}"
    tc.id = "call-1"
    tool_choice = MagicMock()
    tool_choice.message.tool_calls = [tc]
    tool_choice.message.model_dump.return_value = {
        "role": "assistant",
        "tool_calls": [],
    }
    # Second call: final text
    final_choice = MagicMock()
    final_choice.message.tool_calls = None
    final_choice.message.content = "Ferdig."
    client.chat.completions.create.side_effect = [
        MagicMock(choices=[tool_choice]),
        MagicMock(choices=[final_choice]),
    ]
    mock_client.return_value = (client, "model")

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    result = chat_with_tools("analyser", "123", 1, db)
    assert result["answer"] == "Ferdig."
    assert len(result["tool_calls_made"]) == 1
    assert result["tool_calls_made"][0]["tool"] == "run_coverage_gap"
