# LLM token observability

## Why this matters

Every call to Foundry (`gpt-5.4-mini`) or Vertex (`gemini-2.5-flash`)
records prompt + completion token counts as OpenTelemetry histograms.
Without a dashboard, a prompt regression that 10× token cost per call is
invisible until the monthly invoice lands. Shipping this doc + the
Terraform saved-searches means the queries are one click away in the
Azure portal under **Log Analytics → Saved searches → broker-llm**.

## What's instrumented

Both LLM adapters call `record_vertex_token_usage` or the Foundry
equivalent after every response. The histograms:

| Metric | Unit | Attributes |
|---|---|---|
| `llm.tokens.prompt` | `{token}` | `provider` (`foundry`, `vertex_ai`), `model` (`gpt-5.4-mini`, `gemini-2.5-flash`) |
| `llm.tokens.completion` | `{token}` | same |
| `llm.calls` | `{call}` (counter) | `provider`, `outcome` (`success`, `error`) |
| `llm.duration` | `ms` | `provider`, `model` |

Source of truth: `api/telemetry.py` + the two adapters at
`api/adapters/foundry_llm_adapter.py` and
`api/telemetry.py:record_vertex_token_usage`.

## Where the data lives

OTel metrics flow through `configure_azure_monitor` (API startup) into
the workspace-based App Insights at `appi-broker-accelerator-prod`,
which stores them in the linked Log Analytics workspace
`law-prod-brokeraccelerator`. Custom metrics land in the
`customMetrics` table; aggregated views also show up under
**Monitoring → Metrics** in the App Insights blade.

## Saved queries (KQL)

All three below are shipped as `azurerm_log_analytics_saved_search`
resources in `infra/terraform/monitoring.tf`. They show up in the
portal under the `broker-llm` category after `terraform apply`.

### Tokens by provider + model, last 24 h

```kusto
customMetrics
| where timestamp > ago(24h)
| where name in ("llm.tokens.prompt", "llm.tokens.completion")
| extend provider = tostring(customDimensions.provider),
         model    = tostring(customDimensions.model)
| summarize total_tokens = sum(valueSum) by name, provider, model
| order by total_tokens desc
```

Shows which model is burning the most tokens overall. A sudden
appearance of a new `model` row, or a 10× jump against the previous
day, is a signal.

### Tokens per call trend (hour-bucketed)

```kusto
customMetrics
| where timestamp > ago(7d)
| where name == "llm.tokens.prompt"
| extend provider = tostring(customDimensions.provider),
         model    = tostring(customDimensions.model)
| summarize avg_prompt = sum(valueSum) / sum(valueCount)
    by bin(timestamp, 1h), provider, model
| render timechart
```

Average prompt tokens per call. A prompt-regression bug usually shows
up as a step-change in the `avg_prompt` line rather than a gradual
drift. Swap `llm.tokens.prompt` → `llm.tokens.completion` to watch the
output side.

### Call volume vs error rate

```kusto
customMetrics
| where timestamp > ago(24h)
| where name == "llm.calls"
| extend provider = tostring(customDimensions.provider),
         outcome  = tostring(customDimensions.outcome)
| summarize calls = sum(valueCount) by bin(timestamp, 5m), provider, outcome
| render timechart
```

Separates `success` from `error` per provider. Useful during incidents
to check if one provider is quota-limited while the other is healthy.

## Cost back-of-envelope

Current list prices (retail, not Antire Azure commitment):

- `gpt-5.4-mini` via Foundry ≈ $0.15 / 1M input tokens, $0.60 / 1M output
- `gemini-2.5-flash` via Vertex AI ≈ $0.075 / 1M input, $0.30 / 1M output

Multiply the "tokens by provider + model" query totals by the rate to
get daily run-rate. If prod gets to the point where a single-digit
percent of revenue is LLM cost, wire these queries into a Workbook +
an `azurerm_scheduled_query_rules_alert` firing on $/hour thresholds.
Not worth the complexity until we have a baseline.

## When to add an alert

Don't yet — we have no baseline. After ~2 weeks of prod data, pick a
7-day moving average for `avg_prompt` and alert on `>2×` vs that.
Ruleset lives in `monitoring.tf`; follow the existing
`azurerm_monitor_metric_alert` pattern.
