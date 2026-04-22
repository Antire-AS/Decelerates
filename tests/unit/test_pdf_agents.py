"""Unit tests for api/services/pdf_agents.py — agentic IR discovery loops.

All external calls (Anthropic, Azure OpenAI, DDG) are mocked.
Tests cover the orchestrator, Claude agent, Azure OpenAI agent, and
the DDG fallback path. Gemini AI-Studio paths were deleted 2026-04-22
after measured 2/20 recall; see docs/decisions/2026-04-22-pdf-agents-recall.md.
"""

import json
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.modules.setdefault("api.services.pdf_background", MagicMock())


# ── helpers ──────────────────────────────────────────────────────────────────


def _make_tool_use_block(tool_id: str, name: str, input_dict: dict):
    block = MagicMock()
    block.type = "tool_use"
    block.name = name
    block.id = tool_id
    block.input = input_dict
    del block.text
    return block


def _make_text_block(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _make_response(stop_reason: str, content: list):
    resp = MagicMock()
    resp.stop_reason = stop_reason
    resp.content = content
    return resp


# ── _run_tool ────────────────────────────────────────────────────────────────


def test_run_tool_web_search_delegates_to_ddg():
    """After the 2026-04-22 Gemini removal, web_search uses DDG only.
    Phase 2 of the redesign will swap DDG → Bing."""
    from api.services.pdf_agents import _run_tool

    with patch(
        "api.services.pdf_agents._ddg_search_results",
        return_value=[{"url": "http://x", "title": "X"}],
    ):
        result = _run_tool("web_search", {"query": "test"})
    assert result == [{"url": "http://x", "title": "X"}]


def test_run_tool_fetch_url_delegates():
    from api.services.pdf_agents import _run_tool

    with patch(
        "api.services.pdf_agents._fetch_url_content", return_value={"text": "hi"}
    ):
        result = _run_tool("fetch_url", {"url": "http://x.com"})
    assert result == {"text": "hi"}


def test_run_tool_unknown_returns_error():
    from api.services.pdf_agents import _run_tool

    result = _run_tool("unknown_tool", {})
    assert "error" in result


# ── _agent_system_prompt ─────────────────────────────────────────────────────


def test_agent_system_prompt_contains_company_info():
    from api.services.pdf_agents import _agent_system_prompt

    prompt = _agent_system_prompt(
        "TestCo", "123456789", "https://testco.no", [2023, 2024]
    )
    assert "TestCo" in prompt
    assert "123456789" in prompt
    assert "2023" in prompt
    assert "2024" in prompt


# ── _agent_discover_pdfs_claude ──────────────────────────────────────────────


def test_claude_agent_returns_pdf_links(monkeypatch):
    """Turn 1: fetch_url tool call. Turn 2: end_turn with JSON pdf list."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    pdf_url = "https://example.com/annual_report_2023.pdf"
    final_json = json.dumps(
        [{"year": 2023, "pdf_url": pdf_url, "label": "Annual Report 2023"}]
    )

    turn1 = _make_response(
        "tool_use",
        [_make_tool_use_block("tu_1", "fetch_url", {"url": "https://example.com/ir"})],
    )
    turn2 = _make_response("end_turn", [_make_text_block(final_json)])

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [turn1, turn2]
    fetch_result = {"text": "IR page", "pdf_links": [pdf_url], "page_links": []}

    with (
        patch("anthropic.Anthropic", return_value=mock_client),
        patch("api.services.pdf_agents._fetch_url_content", return_value=fetch_result),
    ):
        from api.services.pdf_agents import _agent_discover_pdfs_claude

        result = _agent_discover_pdfs_claude(
            "123456789", "Test AS", "https://example.com", [2023], "test-key"
        )
    assert len(result) == 1
    assert result[0]["pdf_url"] == pdf_url
    assert result[0]["year"] == 2023


def test_claude_agent_calls_fetch_url_tool(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    turn1 = _make_response(
        "tool_use",
        [_make_tool_use_block("tu_99", "fetch_url", {"url": "https://ir.example.com"})],
    )
    turn2 = _make_response("end_turn", [_make_text_block("[]")])

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [turn1, turn2]
    fetch_result = {"text": "page", "pdf_links": [], "page_links": []}

    with (
        patch("anthropic.Anthropic", return_value=mock_client),
        patch(
            "api.services.pdf_agents._fetch_url_content", return_value=fetch_result
        ) as mock_fetch,
    ):
        from api.services.pdf_agents import _agent_discover_pdfs_claude

        _agent_discover_pdfs_claude("111", "X AS", None, [2023], "test-key")
    mock_fetch.assert_called_once_with("https://ir.example.com")


def test_claude_agent_returns_empty_on_end_turn_without_json(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    turn1 = _make_response(
        "end_turn", [_make_text_block("Beklager, ingen PDF-er funnet.")]
    )
    mock_client = MagicMock()
    mock_client.messages.create.return_value = turn1

    with patch("anthropic.Anthropic", return_value=mock_client):
        from api.services.pdf_agents import _agent_discover_pdfs_claude

        result = _agent_discover_pdfs_claude("111", "X AS", None, [2023], "test-key")
    assert result == []


def test_claude_agent_stops_after_end_turn(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    turn1 = _make_response("end_turn", [_make_text_block("[]")])
    mock_client = MagicMock()
    mock_client.messages.create.return_value = turn1

    with patch("anthropic.Anthropic", return_value=mock_client):
        from api.services.pdf_agents import _agent_discover_pdfs_claude

        _agent_discover_pdfs_claude("111", "X AS", None, [2023], "test-key")
    assert mock_client.messages.create.call_count == 1


def test_claude_agent_parses_markdown_wrapped_json(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    pdf_url = "https://example.com/report_2022.pdf"
    raw = f'```json\n[{{"year": 2022, "pdf_url": "{pdf_url}", "label": "Report"}}]\n```'
    turn1 = _make_response("end_turn", [_make_text_block(raw)])
    mock_client = MagicMock()
    mock_client.messages.create.return_value = turn1

    with patch("anthropic.Anthropic", return_value=mock_client):
        from api.services.pdf_agents import _agent_discover_pdfs_claude

        result = _agent_discover_pdfs_claude("111", "X AS", None, [2022], "test-key")
    assert len(result) == 1
    assert result[0]["pdf_url"] == pdf_url


# ── Azure OpenAI agent ───────────────────────────────────────────────────────


def test_azure_openai_agent_returns_empty_without_keys():
    from api.services.pdf_agents import _agent_discover_pdfs_azure_openai

    with patch.dict("os.environ", {}, clear=True):
        result = _agent_discover_pdfs_azure_openai("123", "Co", None, [2023])
    assert result == []


def test_azure_openai_agent_parses_stop_response():
    from api.services.pdf_agents import _agent_discover_pdfs_azure_openai

    pdf_json = json.dumps(
        [{"year": 2023, "pdf_url": "https://x.com/a.pdf", "label": "AR"}]
    )
    msg = SimpleNamespace(content=pdf_json, tool_calls=None)
    msg.model_dump = lambda exclude_unset=False: {
        "role": "assistant",
        "content": pdf_json,
    }
    choice = SimpleNamespace(message=msg, finish_reason="stop")
    response = SimpleNamespace(choices=[choice])

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = response

    with (
        patch.dict(
            "os.environ",
            {
                "AZURE_OPENAI_ENDPOINT": "https://oai.azure.com",
                "AZURE_OPENAI_API_KEY": "key",
            },
        ),
        patch("openai.AzureOpenAI", return_value=mock_client),
    ):
        result = _agent_discover_pdfs_azure_openai("123", "Co", None, [2023])
    assert len(result) == 1
    assert result[0]["year"] == 2023


def test_azure_openai_agent_handles_tool_call_then_stop():
    from api.services.pdf_agents import _agent_discover_pdfs_azure_openai

    tc = SimpleNamespace(
        id="tc_1",
        function=SimpleNamespace(name="web_search", arguments='{"query":"test"}'),
    )
    msg1 = SimpleNamespace(content=None, tool_calls=[tc])
    msg1.model_dump = lambda exclude_unset=False: {
        "role": "assistant",
        "tool_calls": [{"id": "tc_1"}],
    }
    choice1 = SimpleNamespace(message=msg1, finish_reason="tool_calls")
    resp1 = SimpleNamespace(choices=[choice1])

    pdf_json = json.dumps(
        [{"year": 2024, "pdf_url": "https://x.com/b.pdf", "label": "AR"}]
    )
    msg2 = SimpleNamespace(content=pdf_json, tool_calls=None)
    msg2.model_dump = lambda exclude_unset=False: {
        "role": "assistant",
        "content": pdf_json,
    }
    choice2 = SimpleNamespace(message=msg2, finish_reason="stop")
    resp2 = SimpleNamespace(choices=[choice2])

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [resp1, resp2]

    with (
        patch.dict(
            "os.environ",
            {
                "AZURE_OPENAI_ENDPOINT": "https://oai.azure.com",
                "AZURE_OPENAI_API_KEY": "key",
            },
        ),
        patch("openai.AzureOpenAI", return_value=mock_client),
        patch("api.services.pdf_agents._run_tool", return_value=[{"url": "http://x"}]),
    ):
        result = _agent_discover_pdfs_azure_openai("123", "Co", None, [2024])
    assert len(result) == 1


# ── _agent_discover_pdfs (orchestrator) ──────────────────────────────────────


def test_orchestrator_tries_foundry_first():
    from api.services.pdf_agents import _agent_discover_pdfs

    expected = [{"year": 2023, "url": "https://x.com/a.pdf", "label": "annual"}]
    with patch("api.services.pdf_agents_v2.agent_discover_pdfs", return_value=expected):
        result = _agent_discover_pdfs("123", "TestCo", None, [2023])
    assert result == expected


def test_orchestrator_falls_back_to_claude_when_foundry_empty():
    from api.services.pdf_agents import _agent_discover_pdfs

    expected = [{"year": 2023, "pdf_url": "https://x.com/a.pdf", "label": "AR"}]
    with (
        patch("api.services.pdf_agents_v2.agent_discover_pdfs", return_value=[]),
        patch.dict("os.environ", {"ANTHROPIC_API_KEY": "real-key"}),
        patch(
            "api.services.pdf_agents._agent_discover_pdfs_claude", return_value=expected
        ),
    ):
        result = _agent_discover_pdfs("123", "TestCo", None, [2023])
    assert result == expected


def test_orchestrator_returns_empty_when_all_fail():
    from api.services.pdf_agents import _agent_discover_pdfs

    with (
        patch.dict("os.environ", {}, clear=True),
        patch(
            "api.services.pdf_agents._agent_discover_pdfs_azure_openai", return_value=[]
        ),
    ):
        result = _agent_discover_pdfs("123", "TestCo", None, [2023])
    assert result == []


def test_orchestrator_skips_claude_when_key_is_placeholder():
    from api.services.pdf_agents import _agent_discover_pdfs

    with (
        patch.dict("os.environ", {"ANTHROPIC_API_KEY": "your_key_here"}),
        patch(
            "api.services.pdf_agents._agent_discover_pdfs_azure_openai", return_value=[]
        ) as m_az,
    ):
        result = _agent_discover_pdfs("123", "Co", None, [2023])
    assert result == []
    m_az.assert_called_once()


# ── _discover_ir_pdfs (DDG fallback) ─────────────────────────────────────────


def test_discover_ir_pdfs_returns_empty_when_no_urls():
    from api.services.pdf_agents import _discover_ir_pdfs

    with patch("api.services.pdf_agents._search_all_annual_pdfs", return_value=[]):
        assert _discover_ir_pdfs("123", "Co", None, [2023]) == []


def test_discover_ir_pdfs_parses_llm_response():
    from api.services.pdf_agents import _discover_ir_pdfs

    llm_resp = json.dumps(
        [{"year": 2023, "pdf_url": "https://x.com/a.pdf", "label": "AR"}]
    )
    with (
        patch(
            "api.services.pdf_agents._search_all_annual_pdfs",
            return_value=["https://x.com/a.pdf"],
        ),
        patch("api.services.pdf_agents._llm_answer_raw", return_value=llm_resp),
    ):
        result = _discover_ir_pdfs("123", "Co", None, [2023])
    assert len(result) == 1


def test_discover_ir_pdfs_returns_empty_when_llm_returns_none():
    from api.services.pdf_agents import _discover_ir_pdfs

    with (
        patch(
            "api.services.pdf_agents._search_all_annual_pdfs",
            return_value=["https://x.com/a.pdf"],
        ),
        patch("api.services.pdf_agents._llm_answer_raw", return_value=None),
    ):
        assert _discover_ir_pdfs("123", "Co", None, [2023]) == []


def test_discover_ir_pdfs_handles_malformed_json_with_regex():
    from api.services.pdf_agents import _discover_ir_pdfs

    raw = 'Some preamble [{"year": 2024, "pdf_url": "https://x.com/b.pdf", "label": "B"}] trailing'
    with (
        patch(
            "api.services.pdf_agents._search_all_annual_pdfs",
            return_value=["https://x.com/b.pdf"],
        ),
        patch("api.services.pdf_agents._llm_answer_raw", return_value=raw),
    ):
        result = _discover_ir_pdfs("123", "Co", None, [2024])
    assert len(result) == 1
    assert result[0]["year"] == 2024
