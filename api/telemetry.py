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
