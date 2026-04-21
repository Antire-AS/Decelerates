"""Unit tests for Vertex AI token metering (Phase 4 follow-up).

Foundry side is tested in test_foundry_llm.py; this file covers the
Vertex generate_content → OTel `llm.tokens.*` wiring added in
`api/telemetry.py::record_vertex_token_usage`.
"""

from types import SimpleNamespace
from unittest.mock import patch


def test_vertex_usage_records_prompt_and_completion():
    """A Vertex AI response with usage_metadata lands on both histograms
    with provider=vertex_ai and the passed model label."""
    from api import telemetry

    usage = SimpleNamespace(
        prompt_token_count=1234,
        candidates_token_count=567,
        total_token_count=1801,
    )
    resp = SimpleNamespace(usage_metadata=usage, text="irrelevant")

    with (
        patch.object(telemetry, "llm_tokens_prompt") as prompt_hist,
        patch.object(telemetry, "llm_tokens_completion") as completion_hist,
    ):
        telemetry.record_vertex_token_usage(resp, "gemini-2.5-flash")

    prompt_hist.record.assert_called_once_with(
        1234, {"provider": "vertex_ai", "model": "gemini-2.5-flash"}
    )
    completion_hist.record.assert_called_once_with(
        567, {"provider": "vertex_ai", "model": "gemini-2.5-flash"}
    )


def test_vertex_usage_silently_ignores_missing_metadata():
    """Some Vertex responses — e.g. tool-call-only turns in an agent loop —
    omit usage_metadata. Recorder must be a silent no-op, never raise."""
    from api import telemetry

    resp = SimpleNamespace(text="no usage here", usage_metadata=None)

    with (
        patch.object(telemetry, "llm_tokens_prompt") as prompt_hist,
        patch.object(telemetry, "llm_tokens_completion") as completion_hist,
    ):
        telemetry.record_vertex_token_usage(resp, "gemini-2.5-flash")

    prompt_hist.record.assert_not_called()
    completion_hist.record.assert_not_called()


def test_vertex_usage_skips_zero_counts():
    """If Vertex returns zero tokens (degenerate case), we don't clutter
    the histogram with zero-value samples."""
    from api import telemetry

    usage = SimpleNamespace(prompt_token_count=0, candidates_token_count=0)
    resp = SimpleNamespace(usage_metadata=usage)

    with (
        patch.object(telemetry, "llm_tokens_prompt") as prompt_hist,
        patch.object(telemetry, "llm_tokens_completion") as completion_hist,
    ):
        telemetry.record_vertex_token_usage(resp, "gemini-2.5-flash")

    prompt_hist.record.assert_not_called()
    completion_hist.record.assert_not_called()


def test_vertex_usage_falls_back_to_unknown_model():
    """A missing/empty model string resolves to `unknown` in the attrs so
    the App Insights query can still group by model."""
    from api import telemetry

    usage = SimpleNamespace(prompt_token_count=10, candidates_token_count=5)
    resp = SimpleNamespace(usage_metadata=usage)

    with patch.object(telemetry, "llm_tokens_prompt") as prompt_hist:
        telemetry.record_vertex_token_usage(resp, "")

    prompt_hist.record.assert_called_once_with(
        10, {"provider": "vertex_ai", "model": "unknown"}
    )


def test_vertex_usage_swallows_telemetry_exceptions():
    """If the histogram raises for any reason, the caller still completes —
    metering must never fail the LLM extraction path."""
    from api import telemetry

    usage = SimpleNamespace(prompt_token_count=10, candidates_token_count=5)
    resp = SimpleNamespace(usage_metadata=usage)

    with patch.object(telemetry, "llm_tokens_prompt") as prompt_hist:
        prompt_hist.record.side_effect = RuntimeError("otel exporter down")
        # Should not raise:
        telemetry.record_vertex_token_usage(resp, "gemini-2.5-flash")
