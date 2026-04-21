# `tests/manual/` — opt-in measurement harnesses

Everything under this directory is **opt-in**. The tests here make real
API calls (LLM providers, external web fetches), cost money, and take
minutes to run. They are guarded by environment variables so they NEVER
execute in CI and never load unless you explicitly ask.

## What's in here

- `test_pdf_agent_recall.py` — measures IR-PDF discovery recall per
  provider (Azure OpenAI, Anthropic Claude, Gemini AI-Studio) against
  a 20-company Norwegian corpus. Required to decide Option B vs C in
  [`docs/superpowers/plans/2026-04-21-pdf-agents-cleanup.md`](../../docs/superpowers/plans/2026-04-21-pdf-agents-cleanup.md).
  Gated on `PDF_AGENT_RECALL=1` + provider API keys.

## Why this directory exists separately

The auto-discovered `tests/unit` and `tests/integration` trees must be
fast and deterministic — anything flaky or slow there breaks the CI
gate for everyone. Harnesses here are the opposite: slow, flaky
(external providers), and sometimes expensive. Putting them in their
own directory with their own skip guards keeps the main suites clean.

## How to run

Each harness documents its own activation inputs at the top of the
file. The common pattern:

```bash
PDF_AGENT_RECALL=1 \
  ANTHROPIC_API_KEY=sk-ant-... \
  GEMINI_API_KEY=AI... \
  AZURE_OPENAI_API_KEY=... AZURE_OPENAI_ENDPOINT=https://... \
  uv run python -m pytest tests/manual/test_pdf_agent_recall.py -sv
```

The `-s` flag disables pytest output capture so the harness's summary
`print()` lines reach your terminal — that's where the measurement
lives, since these tests don't assert against thresholds.
