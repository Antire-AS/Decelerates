"""OTel custom metric instruments for Broker Accelerator.

Imported by services to record LLM call counts/durations and PDF extraction metrics.
When APPLICATIONINSIGHTS_CONNECTION_STRING is set and configure_azure_monitor() has run
(in api/main.py), these are exported to Azure Monitor. Otherwise they are no-ops — unit
tests and local dev without App Insights require no extra setup.
"""

from opentelemetry import metrics

_meter = metrics.get_meter("broker-accelerator", "1.0.0")

llm_calls = _meter.create_counter(
    name="llm.calls",
    unit="{call}",
    description="LLM calls completed, by provider and outcome",
)
llm_duration_ms = _meter.create_histogram(
    name="llm.duration",
    unit="ms",
    description="LLM call wall-clock duration in milliseconds",
)
# Token metering (Phase 4 of application-hardening plan). Caught the need
# from the 2026-04-21 gap audit — prompt regressions could 10× Azure cost
# overnight and only surface at invoice time. Record prompt + completion
# counts on every Foundry call so a cost spike shows up in App Insights
# the moment it starts.
llm_tokens_prompt = _meter.create_histogram(
    name="llm.tokens.prompt",
    unit="{token}",
    description="Prompt tokens consumed per LLM call (by provider + model)",
)
llm_tokens_completion = _meter.create_histogram(
    name="llm.tokens.completion",
    unit="{token}",
    description="Completion tokens emitted per LLM call (by provider + model)",
)
pdf_extractions = _meter.create_counter(
    name="pdf.extractions",
    unit="{extraction}",
    description="PDF extraction attempts by outcome (success/error)",
)
pdf_extraction_duration_ms = _meter.create_histogram(
    name="pdf.extraction_duration",
    unit="ms",
    description="PDF extraction wall-clock duration in milliseconds",
)
