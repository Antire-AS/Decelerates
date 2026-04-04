"""Unit tests for the Claude agentic PDF discovery loop.

All external calls (anthropic.Anthropic, _fetch_url_content) are mocked.
Tests verify the 2-turn tool-use exchange and correct JSON parsing.
"""
import json
from unittest.mock import MagicMock, patch, call


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_tool_use_block(tool_id: str, name: str, input_dict: dict):
    block = MagicMock()
    block.type = "tool_use"
    block.name = name
    block.id = tool_id
    block.input = input_dict
    # text attribute absent → hasattr check returns False
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


# ── Two-turn happy path ───────────────────────────────────────────────────────

def test_claude_agent_returns_pdf_links(monkeypatch):
    """Turn 1: fetch_url tool call. Turn 2: end_turn with JSON pdf list."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    pdf_url = "https://example.com/annual_report_2023.pdf"
    final_json = json.dumps([{"year": 2023, "pdf_url": pdf_url, "label": "Annual Report 2023"}])

    turn1 = _make_response("tool_use", [_make_tool_use_block("tu_1", "fetch_url", {"url": "https://example.com/ir"})])
    turn2 = _make_response("end_turn", [_make_text_block(final_json)])

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [turn1, turn2]

    fetch_result = {"text": "IR page", "pdf_links": [pdf_url], "page_links": []}

    with patch("anthropic.Anthropic", return_value=mock_client):
        with patch("api.services.pdf_agents._fetch_url_content", return_value=fetch_result):
            from api.services.pdf_agents import _agent_discover_pdfs_claude
            result = _agent_discover_pdfs_claude(
                orgnr="123456789",
                navn="Test AS",
                hjemmeside="https://example.com",
                target_years=[2023],
                api_key="test-key",
            )

    assert len(result) == 1
    assert result[0]["pdf_url"] == pdf_url
    assert result[0]["year"] == 2023


def test_claude_agent_calls_fetch_url_tool(monkeypatch):
    """Verify that the fetch_url tool result is sent back in turn 2 user message."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    turn1 = _make_response("tool_use", [_make_tool_use_block("tu_99", "fetch_url", {"url": "https://ir.example.com"})])
    turn2 = _make_response("end_turn", [_make_text_block("[]")])

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [turn1, turn2]

    fetch_result = {"text": "page", "pdf_links": [], "page_links": []}

    with patch("anthropic.Anthropic", return_value=mock_client):
        with patch("api.services.pdf_agents._fetch_url_content", return_value=fetch_result) as mock_fetch:
            from api.services.pdf_agents import _agent_discover_pdfs_claude
            _agent_discover_pdfs_claude("111", "X AS", None, [2023], "test-key")

    mock_fetch.assert_called_once_with("https://ir.example.com")
    # Second create() call must include the tool_result message
    second_call_messages = mock_client.messages.create.call_args_list[1][1]["messages"]
    user_tool_result = next(m for m in second_call_messages if m["role"] == "user" and isinstance(m["content"], list))
    assert user_tool_result["content"][0]["tool_use_id"] == "tu_99"


def test_claude_agent_returns_empty_on_end_turn_without_json(monkeypatch):
    """If the model ends without returning valid JSON, result is empty list."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    turn1 = _make_response("end_turn", [_make_text_block("Beklager, ingen PDF-er funnet.")])

    mock_client = MagicMock()
    mock_client.messages.create.return_value = turn1

    with patch("anthropic.Anthropic", return_value=mock_client):
        from api.services.pdf_agents import _agent_discover_pdfs_claude
        result = _agent_discover_pdfs_claude("111", "X AS", None, [2023], "test-key")

    assert result == []


def test_claude_agent_stops_after_end_turn(monkeypatch):
    """Once stop_reason == end_turn, no further messages.create calls are made."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    turn1 = _make_response("end_turn", [_make_text_block("[]")])
    mock_client = MagicMock()
    mock_client.messages.create.return_value = turn1

    with patch("anthropic.Anthropic", return_value=mock_client):
        from api.services.pdf_agents import _agent_discover_pdfs_claude
        _agent_discover_pdfs_claude("111", "X AS", None, [2023], "test-key")

    assert mock_client.messages.create.call_count == 1


def test_claude_agent_parses_markdown_wrapped_json(monkeypatch):
    """Agent sometimes wraps JSON in ```json ... ``` — must still parse correctly."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    pdf_url = "https://example.com/report_2022.pdf"
    raw = f"```json\n[{{\"year\": 2022, \"pdf_url\": \"{pdf_url}\", \"label\": \"Report\"}}]\n```"
    turn1 = _make_response("end_turn", [_make_text_block(raw)])

    mock_client = MagicMock()
    mock_client.messages.create.return_value = turn1

    with patch("anthropic.Anthropic", return_value=mock_client):
        from api.services.pdf_agents import _agent_discover_pdfs_claude
        result = _agent_discover_pdfs_claude("111", "X AS", None, [2022], "test-key")

    assert len(result) == 1
    assert result[0]["pdf_url"] == pdf_url
