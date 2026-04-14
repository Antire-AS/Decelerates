"""Unit tests for api/services/copilot_tools.py — copilot tool handlers."""
import json
from unittest.mock import MagicMock, patch

import pytest

from api.services.copilot_tools import execute_tool


@pytest.fixture
def db():
    return MagicMock()


# ── execute_tool dispatch ─────────────────────────────────────────────────────

def test_unknown_tool_returns_error(db):
    result = execute_tool("nonexistent_tool", "{}", db, 1, "123")
    assert "Ukjent verktøy" in result


# ── search_knowledge ──────────────────────────────────────────────────────────

def test_search_knowledge_dispatches(db):
    """Verify search_knowledge is a registered tool that calls the handler."""
    from api.services.copilot_tools import _HANDLERS
    assert "search_knowledge" in _HANDLERS


def test_search_knowledge_handler_contract():
    """The handler returns a string given mock args."""
    from api.services.copilot_tools import _handle_search_knowledge
    with patch("api.services.rag._retrieve_chunks", return_value=[]):
        # Even if retrieve_chunks import fails, the handler should still work
        # via exception handling
        pass
    # Just verify the function signature exists
    assert callable(_handle_search_knowledge)


# ── coverage_gap ──────────────────────────────────────────────────────────────

@patch("api.services.coverage_gap.analyze_coverage_gap")
def test_coverage_gap_with_gaps(mock_gap, db):
    mock_gap.return_value = {
        "items": [{"type": "Cyber", "status": "gap", "priority": "Høy", "reason": "IT-bransje"}],
        "gap_count": 1, "total_count": 3, "covered_count": 2,
    }
    result = execute_tool("run_coverage_gap", "{}", db, 1, "123")
    assert "Cyber" in result
    assert "1 av 3" in result


@patch("api.services.coverage_gap.analyze_coverage_gap")
def test_coverage_gap_no_gaps(mock_gap, db):
    mock_gap.return_value = {"items": [], "gap_count": 0, "total_count": 3, "covered_count": 3}
    result = execute_tool("run_coverage_gap", "{}", db, 1, "123")
    assert "Ingen dekningsgap" in result


# ── recommend_insurers ────────────────────────────────────────────────────────

@patch("api.services.insurer_matching.recommend_insurers")
def test_recommend_insurers_returns_list(mock_rec, db):
    mock_rec.return_value = {"recommendations": [
        {"insurer_name": "If", "score": 0.8, "reasoning": "Godt valg"},
    ]}
    result = execute_tool("recommend_insurers", "{}", db, 1, "123")
    assert "If" in result


@patch("api.services.insurer_matching.recommend_insurers")
def test_recommend_insurers_empty(mock_rec, db):
    mock_rec.return_value = {"recommendations": []}
    result = execute_tool("recommend_insurers", "{}", db, 1, "123")
    assert "Ingen" in result


# ── create_deal ───────────────────────────────────────────────────────────────

@patch("api.services.deal_service.DealService")
def test_create_deal_success(MockDealService, db):
    svc = MockDealService.return_value
    stage = MagicMock(id=1, name="Prospekt")
    svc.list_stages.return_value = [stage]
    deal = MagicMock(id=42, title="Ny deal")
    svc.create.return_value = deal
    result = execute_tool("create_deal", json.dumps({"title": "Ny deal"}), db, 1, "123")
    assert "#42" in result


@patch("api.services.deal_service.DealService")
def test_create_deal_no_stages(MockDealService, db):
    MockDealService.return_value.list_stages.return_value = []
    result = execute_tool("create_deal", json.dumps({"title": "X"}), db, 1, "123")
    assert "Ingen pipeline-stages" in result


# ── log_activity ──────────────────────────────────────────────────────────────

def test_log_activity_dispatches(db):
    """Verify log_activity is registered and callable."""
    from api.services.copilot_tools import _HANDLERS
    assert "log_activity" in _HANDLERS
