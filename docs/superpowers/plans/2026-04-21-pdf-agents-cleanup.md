# pdf_agents.py cleanup — measure first, then decide

> **For agentic workers:** This plan has a *decision branch* — Task 2's
> outcome decides whether Task 3 is "delete code" or "leave code and
> close the plan." Do not run Task 3 without Task 2's output in hand.

**Goal:** Decide whether `api/services/pdf_agents.py` (608 lines, three
LLM provider agent loops) can be cleaned up to Azure-only (−335 LOC) or
whether the multi-provider fallback genuinely improves recall enough to
justify keeping it.

**Architecture:** This isn't a refactor plan — it's a measurement +
possible-deletion plan. The expensive part is gathering data about
real-world IR-PDF discovery recall per provider. The cheap part is the
subsequent code deletion *if* the data supports it.

**Tech stack:** Python + the existing `pytest` harness + real calls to
Anthropic + Gemini AI-Studio + Azure OpenAI + DuckDuckGo fallback.

---

## Background

`api/services/pdf_agents.py` orchestrates four fallback providers to
discover annual-report PDFs for Norwegian companies. In fallback order:

1. Azure OpenAI tool-use (`_agent_discover_pdfs_azure_openai`)
2. Anthropic Claude tool-use (`_agent_discover_pdfs_claude`) — uses
   Anthropic's native `web_search_20250305` tool
3. Gemini AI-Studio two-phase (`_agent_discover_pdfs_gemini`) — uses
   Google Search grounding for the first phase
4. DuckDuckGo per-year URL pattern search (`_discover_ir_pdfs`)

`CLAUDE.md:432–435` explicitly calls this a deliberate deviation from
the rest of the LLM stack (which consolidated on Foundry + Vertex with
no fallback): "reliability beats simplicity there."

**But**: three of those four paths import legacy SDKs (`anthropic`,
`google.genai` AI-Studio, `openai` AzureOpenAI) and carry three env
vars (`ANTHROPIC_API_KEY`, `GEMINI_API_KEY[_2/_3]`, `AZURE_OPENAI_*`).
If Azure + DDG is good enough, deleting the other two saves 335 LOC and
simplifies env-var management.

The question we cannot answer from the code alone: **how much recall do
the Claude and Gemini branches actually contribute?** The orchestrator
short-circuits on the first success, so Azure returning N results
hides whether Claude/Gemini would have found the *same* N or *more*.

## Scope check

One sub-project: a measurement harness that runs the agents
side-by-side on a fixed company sample and reports per-provider
recall. All tasks live in the same worktree / PR. Do not break this
plan into sub-plans.

---

## File structure

- Create: `tests/manual/test_pdf_agent_recall.py` — **not** an
  auto-discovered test. Opt-in harness gated on `PDF_AGENT_RECALL=1`
  and required API keys. Skipped in CI.
- Create: `docs/decisions/2026-04-21-pdf-agents-recall.md` — captures
  the decision + evidence after Task 2 runs.
- Modify (conditional, Task 3 only): `api/services/pdf_agents.py` +
  `tests/unit/test_pdf_agents.py` + `CLAUDE.md` LLM config table.

---

## Task 1: Build the recall harness (no decisions yet)

**Files:**
- Create: `tests/manual/__init__.py` (empty — marker for the directory)
- Create: `tests/manual/test_pdf_agent_recall.py`
- Create: `tests/manual/README.md` (2–3 sentences pointing to the
  harness + how to run it)

**Goal:** A single-file opt-in harness that loops through a fixed
corpus of 20 Norwegian companies (orgnr + navn + hjemmeside), calls
each of the three agent implementations *independently* (not the
fallback-chain orchestrator), and records: did this provider return
≥1 PDF URL, did those URLs HTTP-HEAD OK, did they contain the expected
year in filename or Content-Disposition.

- [ ] **Step 1: Write the corpus constant**

```python
# tests/manual/test_pdf_agent_recall.py

# Twenty Norwegian companies with public IR pages. Mix of large (DNB,
# Equinor, Gjensidige), mid (Schibsted, Orkla, Telenor), small
# (Glommen Mjøsen Skog, Borgestad, Grieg Seafood). Chosen for
# provider diversity: Claude tends to win on known IR portals, Gemini
# on Google-Search-indexed Sanity/Contentful sites, Azure on corporate
# domains with plain filenames.
RECALL_CORPUS: list[tuple[str, str, str]] = [
    ("984851006", "DNB Bank ASA", "https://www.dnb.no"),
    ("995568217", "Gjensidige Forsikring ASA", "https://www.gjensidige.no"),
    ("923609016", "Equinor ASA", "https://www.equinor.com"),
    ("916862037", "Telenor ASA", "https://www.telenor.com"),
    ("933192410", "Schibsted ASA", "https://www.schibsted.com"),
    ("930357618", "Orkla ASA", "https://www.orkla.com"),
    ("999001369", "Yara International ASA", "https://www.yara.com"),
    ("930860675", "Grieg Seafood ASA", "https://www.griegseafood.com"),
    ("947990982", "Kongsberg Gruppen ASA", "https://www.kongsberg.com"),
    ("996525450", "Storebrand ASA", "https://www.storebrand.no"),
    ("956936264", "Veidekke ASA", "https://www.veidekke.com"),
    ("963936060", "Kvaerner ASA", "https://www.kvaerner.com"),
    ("934382404", "NEL ASA", "https://nelhydrogen.com"),
    ("937681140", "Tomra Systems ASA", "https://www.tomra.com"),
    ("913540538", "Aker BP ASA", "https://www.akerbp.com"),
    ("970921093", "REC Silicon ASA", "https://www.recsilicon.com"),
    ("986470668", "Glommen Mjøsen Skog SA", "https://www.glommen-mjosen.no"),
    ("975800761", "Borgestad ASA", "https://www.borgestad.com"),
    ("981211524", "NRC Group ASA", "https://www.nrcgroup.com"),
    ("958935096", "Multiconsult ASA", "https://www.multiconsult.no"),
]
```

- [ ] **Step 2: Skip-if-key-missing guard at module top**

```python
import os
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("PDF_AGENT_RECALL") != "1",
    reason="set PDF_AGENT_RECALL=1 and supply API keys to run",
)
```

- [ ] **Step 3: One test per provider, measuring independently**

Each test takes the corpus, calls the provider directly, records
whether ≥1 URL was returned, and whether at least one URL HTTP-HEADs
OK (200 or 302). Output is a JSON summary at the end via `print()` —
we're not asserting against thresholds yet; that's Task 2's decision.

```python
def _measure_provider(fn, name: str) -> dict:
    results = {}
    for orgnr, navn, site in RECALL_CORPUS:
        try:
            out = fn(orgnr, navn, site, target_years=[2024])
            urls = [u for y in (out or {}).values() for u in y]
            results[orgnr] = {
                "navn": navn,
                "any": bool(urls),
                "urls": urls[:3],
            }
        except Exception as e:
            results[orgnr] = {"navn": navn, "error": str(e)}
    hits = sum(1 for r in results.values() if r.get("any"))
    print(f"\n{name}: {hits}/{len(RECALL_CORPUS)} hits")
    print(f"  detail: {results}")
    return results


def test_azure_recall():
    from api.services.pdf_agents import _agent_discover_pdfs_azure_openai
    _measure_provider(_agent_discover_pdfs_azure_openai, "azure")


def test_claude_recall():
    from api.services.pdf_agents import _agent_discover_pdfs_claude
    _measure_provider(_agent_discover_pdfs_claude, "claude")


def test_gemini_recall():
    from api.services.pdf_agents import _agent_discover_pdfs_gemini
    _measure_provider(_agent_discover_pdfs_gemini, "gemini")
```

- [ ] **Step 4: Commit**

```bash
git add tests/manual/ docs/decisions/
git commit -m "feat(test-harness): opt-in PDF-agent recall measurement"
```

The tests/manual directory is new — include a one-paragraph README.md
explaining that everything under there is opt-in, needs real API keys,
and is never run in CI.

---

## Task 2: Run the harness + capture the decision

**Files:**
- Create: `docs/decisions/2026-04-21-pdf-agents-recall.md`

- [ ] **Step 1: Run all three against the corpus**

```bash
PDF_AGENT_RECALL=1 \
  ANTHROPIC_API_KEY=... \
  GEMINI_API_KEY=... \
  AZURE_OPENAI_API_KEY=... AZURE_OPENAI_ENDPOINT=... \
  uv run python -m pytest tests/manual/test_pdf_agent_recall.py -sv
```

Each run takes ~5 min (20 companies × 3 providers × ~5 s/call). Run
each twice to smooth out transient web fetch failures. Record the
hit counts per provider in a small table.

- [ ] **Step 2: Compute the metric that matters**

The right question isn't raw hit count — it's *marginal recall*. If
Azure found X of 20, how many of the remaining 20–X did Claude find
that Azure missed? Same for Gemini. This is what Task 3's decision
hinges on.

```text
Total companies:                     20
Azure only:                          A
Claude only:                         B
Gemini only:                         C
Azure ∩ Claude:                      AB
Azure ∩ Gemini:                      AG
Claude ∩ Gemini:                     CG
All three:                           ABC
None (DDG fallback territory):       NONE

Marginal recall from Claude        = B + (Azure ∩ Claude - Azure ∩ Claude ∩ others)
Marginal recall from Gemini        = C + (Azure ∩ Gemini - Azure ∩ Gemini ∩ others)
```

- [ ] **Step 3: Write the decision doc**

The template:

```markdown
# Decision: pdf_agents.py provider consolidation

## Context
(link to #177 / #181 / #183; describe the 608-line file and the 3
env vars)

## Measurement
(paste the hit table here)

## Marginal contribution of Claude and Gemini
(numbers from Step 2)

## Decision
[ ] OPTION B — delete Claude + Gemini branches; keep Azure + DDG fallback
[ ] OPTION C — status quo; keep all three

## Rationale
(short narrative tying the numbers to the decision)

## Consequences
(what env vars get deleted, what LOC count changes, what operational
footprint changes)
```

- [ ] **Step 4: Threshold for Option B**

Default threshold: if Claude + Gemini combined contribute **<3 unique
hits of 20** (15% marginal recall), pick B. If ≥3, pick C and document
which IR patterns Claude/Gemini catch that Azure misses.

This threshold is deliberate — a single-digit miss rate is survivable
because DDG is still a 4th fallback and operators can manually paste a
PDF URL via the admin UI. A 15%+ miss rate means brokers would see
empty Profitability tabs more often than the status-quo baseline.

- [ ] **Step 5: Commit the decision**

```bash
git add docs/decisions/2026-04-21-pdf-agents-recall.md
git commit -m "docs: pdf-agents provider consolidation decision"
```

---

## Task 3 (CONDITIONAL): Execute Option B if Task 2 picked it

Skip this task entirely if Task 2's decision was Option C. Close the
plan after committing the decision doc — the measurement work has
value on its own even if no code changes.

**Files:**
- Modify: `api/services/pdf_agents.py` (delete ~335 lines)
- Modify: `tests/unit/test_pdf_agents.py` (delete Claude/Gemini tests)
- Modify: `CLAUDE.md` (update the LLM Config table)
- Modify: `.github/workflows/deploy.yml` (remove env var wiring if any)

### Task 3.1 — Delete Claude branch

- [ ] **Step 1: Delete `_agent_discover_pdfs_claude`** (lines 84–160)
  + its callers inside `_agent_discover_pdfs` orchestrator.
- [ ] **Step 2: Delete matching tests in
  `tests/unit/test_pdf_agents.py`** (lines 108–206, the 6 Claude
  agent + tool-handling tests).
- [ ] **Step 3: Remove `import anthropic` + the `_run_tool` Anthropic
  path** if not shared with Azure.
- [ ] **Step 4: Run unit tests** — `uv run pytest tests/unit -q` must
  still pass. If any test imports `anthropic` transitively, delete
  that stub in `tests/conftest.py` too (search for
  `sys.modules.setdefault("anthropic", MagicMock())`).
- [ ] **Step 5: Commit**

### Task 3.2 — Delete Gemini branch

- [ ] **Step 1: Delete `_gemini_web_search`, `_run_gemini_phase2`,
  `_agent_discover_pdfs_gemini`, `_search_pdf_url_for_year`,
  `_discover_pdfs_per_year_search`** (lines 166–399, ~224 lines).
- [ ] **Step 2: Delete the 15 Gemini tests in
  `tests/unit/test_pdf_agents.py`** (lines 211–452).
- [ ] **Step 3: Remove the AI-Studio Gemini client setup** (but keep
  Vertex AI — that's still used by `api/services/pdf_parse.py`).
- [ ] **Step 4: Run unit tests.**
- [ ] **Step 5: Commit.**

### Task 3.3 — Env var + docs cleanup

- [ ] **Step 1: Remove `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`,
  `GEMINI_API_KEY_2`, `GEMINI_API_KEY_3` from** `api/main.py`
  startup env-var reads, `.github/workflows/deploy.yml` env block,
  `docker-compose.yml` if referenced.
- [ ] **Step 2: Update `CLAUDE.md` LLM Config table** — the "Agentic
  IR PDF discovery" row should now read Azure OpenAI → DuckDuckGo
  only. Drop the "deliberate exception" paragraph too — after
  consolidation, the pipeline matches the rest of the stack's
  no-fallback philosophy.
- [ ] **Step 3: Note in the decision doc that it was executed.**
- [ ] **Step 4: Commit.**

### Task 3.4 — GitHub secret retirement (AFTER merge)

- [ ] Only do this after the PR is merged and a prod deploy has been
  running cleanly for at least 48 h.
- [ ] `gh secret delete ANTHROPIC_API_KEY`
- [ ] `gh secret delete GEMINI_API_KEY` (× 2/3)
- [ ] Revoke the Anthropic + AI-Studio keys at the provider consoles.

---

## No Placeholders

Every task in this plan has concrete steps with real file paths, real
line numbers (from the 2026-04-21 state of `pdf_agents.py`), and real
code blocks for the harness. The decision point in Task 2 *is* the
point — don't try to pre-write Task 3 without Task 2's output, and
don't run Task 3 on vibes.

## Self-Review

- [ ] Task 1 produces an opt-in harness that is 100% CI-safe (skipped
  without `PDF_AGENT_RECALL=1`).
- [ ] Task 2 has a concrete threshold (<3 unique hits → Option B) so
  the decision isn't subjective.
- [ ] Task 3 is explicitly conditional and lists every file that must
  change, not just the main one.

## Execution Handoff

This plan is measurement-first and does not need subagent-driven
execution — Task 1 is a single file, Task 2 is human-run measurement,
Task 3 is conditional. Run it inline.

## Out of scope

- Rewriting any of the agents to Foundry tool-use (Option A from the
  original scoping). Reason: Azure OpenAI is already Foundry-shaped;
  if Option B holds up, we're already there.
- Adding more companies to the recall corpus. 20 is enough to detect
  large effects; tripling the corpus triples the cost without changing
  the decision unless the numbers are borderline.
- Improving the DDG fallback. That's a separate improvement track.
