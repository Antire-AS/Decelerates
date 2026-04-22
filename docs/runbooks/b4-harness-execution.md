# Run the PDF-agent recall harness (B4 Task 2)

## What this is

Task 2 of the pdf_agents cleanup plan
([`docs/superpowers/plans/2026-04-21-pdf-agents-cleanup.md`](../superpowers/plans/2026-04-21-pdf-agents-cleanup.md))
deliberately requires a human-run measurement step. The harness was
shipped in PR #185 and lives at `tests/manual/test_pdf_agent_recall.py`.

It runs each of three agent providers (Azure OpenAI, Anthropic Claude,
Gemini AI-Studio) against a fixed 20-company Norwegian corpus and
records per-company hit + elapsed + error data as JSON. The decision
doc at the end uses marginal recall (what Claude + Gemini find that
Azure misses) to decide Option B (delete Claude + Gemini branches,
−335 LOC) vs Option C (keep all three).

## Cost + time

- ~15 minutes wall-clock (20 companies × 3 providers × ~5 s/call with
  tool-use loops)
- A few USD in combined API spend (tokens + web_search tool calls)
- Network: makes real HTTP fetches to Norwegian company IR pages via
  Playwright + requests fallback

## Prerequisites

- `ANTHROPIC_API_KEY` — Anthropic console key with `claude-haiku-4-5`
  access
- `GEMINI_API_KEY` — Google AI Studio key (from `aistudio.google.com`)
- `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` — broker-accelerator
  deployment keys (check `gh secret list` — they exist as GitHub
  secrets; pull the raw values from Azure Key Vault or from the
  Azure portal under the OpenAI resource)
- `uv` + the repo's venv — standard local dev setup

## Run it

Run ALL THREE providers in one pass so the JSON output files share
a similar timestamp (easier to correlate):

```bash
PDF_AGENT_RECALL=1 \
  ANTHROPIC_API_KEY=$(grep "^ANTHROPIC_API_KEY=" .env | cut -d= -f2-) \
  GEMINI_API_KEY=$(grep "^GEMINI_API_KEY=" .env | cut -d= -f2-) \
  AZURE_OPENAI_API_KEY="<paste from keyvault>" \
  AZURE_OPENAI_ENDPOINT="<paste from keyvault>" \
  uv run python -m pytest \
    tests/manual/test_pdf_agent_recall.py -sv --timeout=1800
```

Expected output (end of run):

```
azure: 14/20 hits → tests/manual/.recall-results/azure-<timestamp>.json
claude: 16/20 hits → tests/manual/.recall-results/claude-<timestamp>.json
gemini: 17/20 hits → tests/manual/.recall-results/gemini-<timestamp>.json
```

## Interpret the result

### Step 1: Build the intersection table

The JSON files under `tests/manual/.recall-results/` have per-orgnr
`{"any_pdf": bool}` entries. Intersect them:

```python
import json
import pathlib

results_dir = pathlib.Path("tests/manual/.recall-results")
by_provider = {}
for p in results_dir.glob("*.json"):
    data = json.loads(p.read_text())
    by_provider[data["provider"]] = {
        orgnr for orgnr, rec in data["per_company"].items()
        if rec.get("any_pdf")
    }

azure  = by_provider["azure"]
claude = by_provider["claude"]
gemini = by_provider["gemini"]

print(f"Azure only:  {len(azure - claude - gemini):>2}")
print(f"Claude only: {len(claude - azure - gemini):>2}")
print(f"Gemini only: {len(gemini - azure - claude):>2}")
print(f"Azure + Claude, no Gemini: {len(azure & claude - gemini):>2}")
print(f"Azure + Gemini, no Claude: {len(azure & gemini - claude):>2}")
print(f"Claude + Gemini, no Azure: {len(claude & gemini - azure):>2}")
print(f"All three:   {len(azure & claude & gemini):>2}")
print(f"None:        {len(set(range(20)) - azure - claude - gemini):>2}")

# What Claude + Gemini find that Azure misses — the marginal contribution
marginal = (claude | gemini) - azure
print(f"\nMARGINAL RECALL vs Azure-only: {len(marginal)}/{20}")
```

### Step 2: Decide against the pre-registered threshold

- **`marginal < 3`** (<15% of corpus) → **Option B**: delete Claude +
  Gemini branches + their 3 env vars. −335 LOC, −3 secrets, one
  less fallback to reason about.
- **`marginal ≥ 3`** → **Option C**: keep all three. Document which
  IR patterns Claude / Gemini catch that Azure misses (the JSON
  output has the URLs as evidence).

### Step 3: Write the decision doc

Create `docs/decisions/2026-04-21-pdf-agents-recall.md` with:

- The raw hit counts
- The intersection table
- Marginal recall value
- Decision (B or C)
- Rationale tying the numbers to the choice
- If B: next step is executing Task 3 of the cleanup plan
- If C: the deliberate-exception comment in `CLAUDE.md:432–435` stands

## If results are borderline

If `marginal = 3` exactly, re-run once. Providers have ~5–10% variance
run-to-run from web fetch flakiness. A tie-breaker re-run gives a
more stable signal without doubling the cost.

## If a provider errors out

The harness catches per-company exceptions and records them in the
JSON. If you see 5+ errors for one provider (e.g. auth failure or
quota exhaustion), that provider's hit count is meaningless; fix the
root cause and re-run just that one test with
`--k test_<provider>_recall`.

## Cost optimisation if you re-run often

The corpus is hard-coded. If you want to iterate on provider prompts,
slice the corpus first:

```python
# Temporary edit in tests/manual/test_pdf_agent_recall.py
RECALL_CORPUS = RECALL_CORPUS[:5]  # first 5 companies only
```

Revert before committing.
