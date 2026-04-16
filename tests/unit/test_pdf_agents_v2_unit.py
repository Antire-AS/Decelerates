"""Unit tests for api/services/pdf_agents_v2.py — Foundry tool-use IR agent."""
import sys
from unittest.mock import MagicMock, patch

sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

import pytest


# ── _execute_ir_tool ─────────────────────────────────────────────────────────


class TestExecuteIrTool:
    def test_web_search_calls_ddg(self):
        from api.services.pdf_agents_v2 import _execute_ir_tool
        with patch("api.services.pdf_agents_v2._ddg_search_results", return_value=[
            {"title": "DNB", "url": "https://dnb.no/ar.pdf", "snippet": "annual report"},
        ]):
            result = _execute_ir_tool("web_search", '{"query": "DNB arsrapport"}')
        assert "DNB" in result

    def test_fetch_url_calls_fetch(self):
        from api.services.pdf_agents_v2 import _execute_ir_tool
        with patch("api.services.pdf_agents_v2._fetch_url_content", return_value={"text": "page content"}):
            result = _execute_ir_tool("fetch_url", '{"url": "https://example.com"}')
        assert "page content" in result

    def test_unknown_tool_returns_error(self):
        from api.services.pdf_agents_v2 import _execute_ir_tool
        result = _execute_ir_tool("unknown_tool", "{}")
        assert "Unknown tool" in result

    def test_handles_invalid_json_args(self):
        from api.services.pdf_agents_v2 import _execute_ir_tool
        with patch("api.services.pdf_agents_v2._ddg_search_results", return_value=[]):
            result = _execute_ir_tool("web_search", "not-json")
        # Should not raise — gracefully defaults to empty args
        assert isinstance(result, str)


# ── _parse_agent_response ────────────────────────────────────────────────────


class TestParseAgentResponse:
    def test_parses_json_with_pdfs_key(self):
        from api.services.pdf_agents_v2 import _parse_agent_response
        text = '{"pdfs": [{"year": 2024, "url": "https://example.com/r.pdf", "label": "annual"}]}'
        result = _parse_agent_response(text)
        assert len(result) == 1
        assert result[0]["year"] == 2024

    def test_parses_bare_list(self):
        from api.services.pdf_agents_v2 import _parse_agent_response
        text = '[{"year": 2023, "url": "https://example.com/r.pdf"}]'
        result = _parse_agent_response(text)
        assert len(result) == 1

    def test_parses_json_in_markdown_code_block(self):
        from api.services.pdf_agents_v2 import _parse_agent_response
        text = 'Here are the results:\n```json\n{"pdfs": [{"year": 2022, "url": "https://ex.com/r.pdf"}]}\n```'
        result = _parse_agent_response(text)
        assert len(result) == 1

    def test_returns_empty_for_non_json(self):
        from api.services.pdf_agents_v2 import _parse_agent_response
        result = _parse_agent_response("I could not find any PDFs.")
        assert result == []


# ── _build_ir_system_prompt ──────────────────────────────────────────────────


class TestBuildIrSystemPrompt:
    def test_contains_company_info(self):
        from api.services.pdf_agents_v2 import _build_ir_system_prompt
        prompt = _build_ir_system_prompt("123456789", "DNB Bank ASA", "https://dnb.no", [2024, 2023])
        assert "DNB Bank ASA" in prompt
        assert "123456789" in prompt
        assert "2024" in prompt
        assert "dnb.no" in prompt


# ── _fallback_ddg_search ────────────────────────────────────────────────────


class TestFallbackDdgSearch:
    def test_returns_pdf_results(self):
        from api.services.pdf_agents_v2 import _fallback_ddg_search
        with patch("api.services.pdf_agents_v2._ddg_search_results", return_value=[
            {"url": "https://example.com/report2024.pdf", "title": "AR"},
        ]):
            result = _fallback_ddg_search("DNB Bank", [2024])
        assert len(result) == 1
        assert result[0]["year"] == 2024

    def test_skips_non_pdf_results(self):
        from api.services.pdf_agents_v2 import _fallback_ddg_search
        with patch("api.services.pdf_agents_v2._ddg_search_results", return_value=[
            {"url": "https://example.com/report.html", "title": "AR"},
        ]):
            result = _fallback_ddg_search("DNB Bank", [2024])
        assert len(result) == 0

    def test_handles_search_exception_gracefully(self):
        from api.services.pdf_agents_v2 import _fallback_ddg_search
        with patch("api.services.pdf_agents_v2._ddg_search_results", side_effect=RuntimeError("down")):
            result = _fallback_ddg_search("DNB Bank", [2024])
        assert result == []


# ── agent_discover_pdfs ──────────────────────────────────────────────────────


class TestAgentDiscoverPdfs:
    def test_function_exists(self):
        """Verify the main entry point is importable."""
        from api.services.pdf_agents_v2 import agent_discover_pdfs
        assert callable(agent_discover_pdfs)
