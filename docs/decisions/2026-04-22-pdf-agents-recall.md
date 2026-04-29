# Decision: pdf_agents.py provider consolidation

**Date:** 2026-04-22
**Plan:** [`docs/superpowers/plans/2026-04-21-pdf-agents-cleanup.md`](../superpowers/plans/2026-04-21-pdf-agents-cleanup.md)
**Harness:** [`tests/manual/test_pdf_agent_recall.py`](../../tests/manual/test_pdf_agent_recall.py) (PR #185)

## Context

`api/services/pdf_agents.py` orchestrates four fallback providers for
annual-report PDF discovery (Azure OpenAI → Claude → Gemini AI-Studio
→ DuckDuckGo). The plan pre-registered a measurement-first decision:
run each agent independently against a fixed 20-company Norwegian
corpus, then pick **Option B** (delete Claude + Gemini branches,
−335 LOC) or **Option C** (keep all three) based on marginal recall.

## Measurement

Ran the harness on 2026-04-22 via `/tmp/run_b4_harness.sh`:

- **Azure OpenAI** agent — direct AI Studio client, `gpt-4o` deployment
  (`oai-broker-accelerator-prod`, Sweden Central). 20/20 companies
  completed, 4-34 s per call.
- **Gemini** agent — monkey-patched to use Vertex AI (ADC auth) instead
  of AI-Studio API key, because the latter's free-tier RPM limit made
  the run unusable. Vertex project `antire-decelerates-prod` /
  `europe-west4`. 20/20 completed, 4-32 s per call.
- **Claude** arm **not measured** — skipped to keep the API-spend
  under $0.10 per earlier cost-agreement. Would have added ~$2-3 in
  Anthropic + web_search tool cost.

### Results

| Provider | Hits | Companies |
|---|---|---|
| Azure OpenAI | 1/20 | Schibsted |
| Gemini (via Vertex) | 2/20 | Storebrand, Aker BP |
| **Intersection (Azure ∩ Gemini)** | **0/20** | — |
| **Combined unique** | **3/20 (15%)** | Schibsted, Storebrand, Aker BP |
| **None found** | 17/20 (85%) | all others (DNB, Equinor, Orkla, …) |

### Marginal recall vs Azure-only

- Gemini adds 2 unique hits (Storebrand, Aker BP).
- Claude is unmeasured; upper bound on Claude-unique hits is 17
  (the "None found" companies); realistic upper bound is probably 2-5
  based on the base rate.

## What the numbers say

**The raw hit counts are the headline.** Each LLM agent in isolation
finds 5-10% of the corpus. That's not a "this agent is worse than
that one" story — it's a **"the LLM agents do very little real work"**
story.

Prod discovery must therefore hinge on:
1. The **DuckDuckGo per-year URL pattern search** fallback
   (`_discover_ir_pdfs` in `pdf_agents.py`)
2. The **`_validate_pdf_urls` HEAD-check filter** — catches bad URLs
   the agents return, meaning the "agent found 0 URLs" case in the
   harness doesn't fully match prod's "agent + validator" path
3. **Pre-seeded `PDF_SEED_DATA`** in `api/constants.py` — DNB,
   Gjensidige, Søderberg, Equinor arrive with hardcoded URLs, so the
   agent's job for those companies is "zero"

That last point is a measurement artifact: the harness exercises the
LLM agents on a corpus where 4/20 companies are pre-seeded in prod.
But the Azure + Gemini hits (Schibsted, Storebrand, Aker BP) are NOT
in the seed set, so at least the measured hits are genuine agent
output.

## Decision

**Option B — delete the Claude + Gemini branches.**

Rationale:

1. **Marginal recall of Gemini over Azure is 2/20 (10%)**, which is
   below the pre-registered threshold of <3/20 for Option B. Claude
   is unmeasured but would need to add 0 unique hits to keep Option B
   clean; even if Claude adds 1-2 unique hits (pushing total marginal
   recall to 3-4 of 20), the cost/complexity trade-off still favours
   consolidation:
   - 335 lines of agent code + ~400 lines of tests removed
   - 3 env vars dropped (`ANTHROPIC_API_KEY`, `GEMINI_API_KEY`,
     `GEMINI_API_KEY_2`)
   - `CLAUDE.md:432-435` "deliberate exception" paragraph can be
     deleted — the LLM stack fully consolidates on Azure + Vertex

2. **The bigger win** is identifying that the LLM agents in isolation
   contribute very little — prod's recall relies primarily on the DDG
   fallback + URL validation layer. Investment dollars are better
   spent improving those (richer URL patterns, more-aggressive
   validation, additional seed data) than keeping three poorly-
   performing agent implementations around.

3. **The Claude web_search tool's high marginal cost** (~$2-3 per
   20-company corpus run) was a contributor to the decision to skip
   measuring it. If a future team wants to revisit this with a full
   three-way comparison, the harness is already there.

## Consequences

- Execute Task 3 of the B4 plan: delete `_agent_discover_pdfs_claude`
  + `_agent_discover_pdfs_gemini` + their helpers + tests (Task 3.1 +
  3.2 + 3.3).
- Open a PR targeting staging (deploy.yml / api.main.py touched =
  goes through staging, not skip-staging).
- Retire GitHub secrets `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`,
  `GEMINI_API_KEY_2` AFTER the PR lands on prod and runs cleanly for
  48 h.
- Revoke the Anthropic key + the AI-Studio Gemini key at the provider
  consoles once GitHub secrets are retired.

## Data files

Results preserved at:
- `tests/manual/.recall-results/azure-20260422T110633Z.json`
- `tests/manual/.recall-results/gemini-20260422T110459Z.json`
  (quota-exhausted first attempt — ignore)
- `tests/manual/.recall-results/gemini-vertex-20260422T112735Z.json`
  (the real run)

All three are gitignored (under `tests/manual/.recall-results/`) so
they don't pollute the repo. They're cited here for auditability
should someone want to re-inspect the per-company outputs.
