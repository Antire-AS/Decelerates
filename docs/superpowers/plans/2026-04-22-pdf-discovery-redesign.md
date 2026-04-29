# PDF Discovery Pipeline Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raise PDF discovery recall from the current measured ~15% (3/20 on a Norwegian corpus with no seed data) to 85–95% by replacing three broken layers (Gemini AI-Studio with busted quota, DDG with bot-detection blocks, Claude disabled) with working equivalents (Vertex AI, Bing Web Search, Anthropic native `web_search_20250305`) plus an expanded seed data set for the top broker companies.

**Architecture:** Keep the 4-layer fallback shape but swap implementations:
1. **Claude with native `web_search_20250305` tool** — highest-recall layer (first-party web search, ~$0.01/call)
2. **Gemini via Vertex AI** — Google Search grounding, no free-tier quota cliff
3. **Azure OpenAI** — no search tool, but useful for tool-use fallback on edge cases
4. **Bing Web Search API** — replaces DDG scraping; 1K queries/month free
5. **`PDF_SEED_DATA` overlay** — still the ground truth for the top ~100 broker-used companies

**Tech stack:** existing Python + FastAPI + Azure, plus new: Bing Search API (Azure Cognitive Services), Anthropic SDK re-enabled.

---

## Scope check

Four phases, three of which can ship independently:

- **Phase 1** (cleanup) — **blocking prerequisite** for rest; deletes the broken Gemini AI-Studio paths so Phase 2/3 have a clean base
- **Phase 2** (Bing) — independent
- **Phase 3** (Claude re-intro) — independent
- **Phase 4** (seed data expansion) — independent, can run in parallel with 2/3

Each phase = one PR. Ship Phase 1 first; Phases 2–4 can interleave.

## File structure

Map of files each phase creates or modifies:

| Phase | Create | Modify |
|---|---|---|
| 1 | — | `api/services/pdf_agents.py` (delete), `tests/unit/test_pdf_agents.py` (delete), `api/main.py` (drop env reads), `CLAUDE.md` (LLM table), `.github/workflows/deploy.yml` (drop env vars) |
| 2 | `api/adapters/bing_search_adapter.py`, `api/ports/driven/web_search_port.py`, `tests/unit/test_bing_search_adapter.py` | `api/services/pdf_web.py` (swap DDG → port), `api/container.py`, `api/main.py` |
| 3 | — | `api/services/pdf_agents.py` (re-add `_agent_discover_pdfs_claude`), `tests/unit/test_pdf_agents.py`, `CLAUDE.md` |
| 4 | — | `api/constants.py` (extend `PDF_SEED_DATA`) |

Each phase has a per-PR harness re-run to measure recall impact. Targets:

| After phase | Expected recall vs current 3/20 |
|---|---|
| 1 | 3/20 (no change — just cleanup) |
| 2 | 10–13/20 (Bing gives real search results) |
| 3 | 14–17/20 (Claude's native web_search adds unique hits) |
| 4 | 18–20/20 (seed data covers remaining long-tail) |

---

## Phase 1 — Option B cleanup

Rationale in `docs/decisions/2026-04-22-pdf-agents-recall.md`. Deleting the measurable-dead Gemini AI-Studio arms and the broken DDG path (Phase 2 replaces DDG; Phase 1 removes only Gemini to keep Phase 2 focused).

### Task 1.1 — Delete Gemini AI-Studio agent path

**Files:**
- Modify: `api/services/pdf_agents.py` (lines 163–399, ~236 lines)
- Modify: `tests/unit/test_pdf_agents.py` (delete Gemini-specific tests, ~15 tests)

- [ ] **Step 1: Write the regression test first**

The orchestrator `_agent_discover_pdfs` still works even without Gemini. Confirm this is tested:

```python
# tests/unit/test_pdf_agents.py — add if missing
def test_orchestrator_falls_from_claude_to_azure_no_gemini(monkeypatch):
    """After Phase 1, Gemini is gone. The chain is Claude → Azure → DDG-replacement."""
    from api.services import pdf_agents
    monkeypatch.setattr(pdf_agents, "_agent_discover_pdfs_claude", lambda *a, **kw: [])
    monkeypatch.setattr(
        pdf_agents, "_agent_discover_pdfs_azure_openai",
        lambda *a, **kw: [{"year": 2024, "pdf_url": "https://x.com/a.pdf", "label": "AR"}],
    )
    result = pdf_agents._agent_discover_pdfs("123", "X AS", "https://x.com", [2024])
    assert len(result) == 1
    assert result[0]["pdf_url"] == "https://x.com/a.pdf"
```

- [ ] **Step 2: Run the test — should PASS currently but FAIL if someone left a Gemini require**

```bash
uv run pytest tests/unit/test_pdf_agents.py::test_orchestrator_falls_from_claude_to_azure_no_gemini -v
```

Expected: PASS (Gemini is a fallback, not required).

- [ ] **Step 3: Delete Gemini code**

Remove from `api/services/pdf_agents.py`:
- `_gemini_web_search` (lines 166–223, 58 lines)
- `_run_gemini_phase2` (lines 225–255, 31 lines)
- `_agent_discover_pdfs_gemini` (lines 258–323, 66 lines)
- `_search_pdf_url_for_year` (lines 329–379, 51 lines)
- `_discover_pdfs_per_year_search` (lines 382–399, 18 lines)
- Gemini-specific imports (`google_genai` for agent paths — keep imports used by Vertex extraction)
- `_GEMINI_FETCH_URL_TOOL` constant
- The Gemini branches inside `_agent_discover_pdfs` orchestrator (lines ~539–572)

- [ ] **Step 4: Delete the matching tests**

In `tests/unit/test_pdf_agents.py` delete:
- `test_gemini_agent_returns_results`
- `test_gemini_agent_retries_on_quota_and_returns_empty`
- `test_gemini_agent_raises_non_quota_error`
- `test_gemini_agent_uses_homepage_fallback_when_phase1_empty`
- `test_run_gemini_phase2_handles_tool_call_loop`
- `test_gemini_web_search_*`
- `test_search_pdf_url_for_year_*`
- Any orchestrator test that asserts on Gemini being called (update to assert on the new chain instead)

- [ ] **Step 5: Run full unit suite**

```bash
uv run pytest tests/unit -q
```

Expected: all tests pass, ~15 tests fewer than before.

- [ ] **Step 6: Commit**

```bash
git add api/services/pdf_agents.py tests/unit/test_pdf_agents.py
git commit -m "refactor(pdf_agents): remove Gemini AI-Studio agent (measured 2/20 recall)"
```

### Task 1.2 — Drop `GEMINI_API_KEY[_2/_3]` env vars

**Files:**
- Modify: `api/main.py` (remove startup env-var reads if any)
- Modify: `.github/workflows/deploy.yml` (remove from ENV_VARS array, lines 114–116)
- Modify: `tests/conftest.py` (no change needed — the stub was for the `google.genai` module not the key)

- [ ] **Step 1: Remove env var wiring in deploy.yml**

```yaml
# .github/workflows/deploy.yml — in the ENV_VARS array
# DELETE THESE THREE LINES (around line 114-116):
#   "GEMINI_API_KEY=${{ secrets.GEMINI_API_KEY }}"
#   "GEMINI_API_KEY_2=${{ secrets.GEMINI_API_KEY_2 }}"
#   "GEMINI_API_KEY_3=${{ secrets.GEMINI_API_KEY_3 }}"
```

Keep the `GCP_VERTEX_AI_*` vars — those are for Vertex-based PDF extraction, not the deleted Gemini AI-Studio agent.

- [ ] **Step 2: Grep for remaining references**

```bash
rg "GEMINI_API_KEY" --type-add 'all:*' -t all --glob '!node_modules' --glob '!.venv'
```

Expected result: 0 hits. If any found, delete.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "chore(deploy): drop GEMINI_API_KEY env vars (agent removed)"
```

### Task 1.3 — Update CLAUDE.md LLM table

**Files:**
- Modify: `CLAUDE.md` (lines 417–435, the LLM Config table + deliberate-exception paragraph)

- [ ] **Step 1: Replace the "Agentic IR PDF discovery" table row**

Old:
```markdown
| **Agentic IR PDF discovery** | Anthropic Claude → Azure OpenAI → Gemini AI Studio → DuckDuckGo | ... | ANTHROPIC_API_KEY, AZURE_OPENAI_*, GEMINI_API_KEY[_2/_3] (legacy, slated for migration) |
```

New (Phase 1 state — Phases 2/3 will update this further):
```markdown
| **Agentic IR PDF discovery** | Azure OpenAI → DuckDuckGo fallback (broken — Phase 2 of 2026-04-22 redesign) | `gpt-4o-mini` | AZURE_OPENAI_* |
```

- [ ] **Step 2: Delete the "deliberate exception" paragraph** (lines ~430–435)

Once all three phases ship, the LLM stack is fully consolidated on Azure + Vertex + Anthropic-for-search (Phase 3) — not a fallback-chain anymore.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(CLAUDE): update LLM table — Gemini agent removed"
```

### Task 1.4 — Ship Phase 1 via staging

- [ ] **Step 1: Push, open PR to `staging`, wait for CI**

```bash
git push -u origin refactor/pdf-agents-phase1
gh pr create --base staging --title "refactor(pdf_agents): Phase 1 — remove Gemini AI-Studio agent"
```

- [ ] **Step 2: After staging deploy green, promote to main** via fresh-branch-off-main + cherry-pick (memory-documented pattern).

- [ ] **Step 3: After prod deploy green + 48h uptime: retire GitHub secrets**

```bash
gh secret delete GEMINI_API_KEY
gh secret delete GEMINI_API_KEY_2
gh secret delete GEMINI_API_KEY_3
```

Revoke the keys at Google AI Studio console.

---

## Phase 2 — Bing Web Search adapter (replaces DDG)

Replace `_search_all_annual_pdfs` (DDG scrape) with a Bing Web Search API call. Bing Search is HTTP-native, has a proper API, and has a 1K-query/month free tier that covers our usage.

### Task 2.1 — Create Azure Cognitive Services Bing Search resource

**Files:**
- Modify: `infra/terraform/monitoring.tf` or a new `infra/terraform/search.tf`

- [ ] **Step 1: Add Terraform resource**

```hcl
resource "azurerm_cognitive_account" "bing_search" {
  name                = "cog-${var.env}-bing-search"
  location            = "global"  # Bing Search is global, not regional
  resource_group_name = azurerm_resource_group.main.name
  kind                = "Bing.Search.v7"
  sku_name            = "F1"  # 1K queries/month free
  tags                = local.tags
}

output "bing_search_key" {
  value     = azurerm_cognitive_account.bing_search.primary_access_key
  sensitive = true
}
```

- [ ] **Step 2: `terraform apply` locally**

Follow `docs/runbooks/terraform-apply-llm-observability.md` for the plan-review-apply dance.

- [ ] **Step 3: Push the key to GitHub secrets + Container App env**

```bash
BING_KEY=$(terraform output -raw bing_search_key)
gh secret set BING_SEARCH_API_KEY --body "$BING_KEY"
# Also add to deploy.yml ENV_VARS array (Task 2.2 covers this)
```

### Task 2.2 — Define port + adapter

**Files:**
- Create: `api/ports/driven/web_search_port.py`
- Create: `api/adapters/bing_search_adapter.py`
- Create: `tests/unit/test_bing_search_adapter.py`

- [ ] **Step 1: Write the port**

```python
# api/ports/driven/web_search_port.py
"""Abstract web search port — lets us swap Bing / Serper / self-hosted
without touching discovery code."""

from abc import ABC, abstractmethod
from typing import List


class WebSearchPort(ABC):
    @abstractmethod
    def search_pdfs(self, query: str, max_results: int = 10) -> List[str]:
        """Return PDF URLs matching `query`, or [] if no results / rate-limited.

        Implementations MUST NOT raise — swallow network errors and return
        empty. Caller distinguishes "search worked but found nothing" from
        "search broke" via logs, not exceptions.
        """
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        """True if the adapter has credentials and can make real calls."""
        ...
```

- [ ] **Step 2: Write the Bing adapter**

```python
# api/adapters/bing_search_adapter.py
"""Bing Web Search v7 API adapter.

Bing returns ~10 results per query by default. Filter to PDFs via the
`+filetype:pdf` operator in the query itself; Bing's native filetype
filter works and returns only .pdf URLs.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

import requests

from api.ports.driven.web_search_port import WebSearchPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BingSearchConfig:
    endpoint: str  # e.g. "https://api.bing.microsoft.com/v7.0/search"
    api_key: Optional[str] = None
    market: str = "en-US"  # BCP-47; Norwegian companies work fine in en-US


class BingSearchAdapter(WebSearchPort):
    def __init__(self, config: BingSearchConfig) -> None:
        self._cfg = config

    def is_configured(self) -> bool:
        return bool(self._cfg.api_key)

    def search_pdfs(self, query: str, max_results: int = 10) -> List[str]:
        if not self.is_configured():
            logger.info("[bing] Not configured — skipping search for %r", query)
            return []
        try:
            resp = requests.get(
                self._cfg.endpoint,
                params={
                    "q": f"{query} filetype:pdf",
                    "count": max_results,
                    "mkt": self._cfg.market,
                    "responseFilter": "Webpages",
                },
                headers={"Ocp-Apim-Subscription-Key": self._cfg.api_key},
                timeout=15,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("[bing] Query %r failed: %s", query, exc)
            return []
        data = resp.json()
        pages = (data.get("webPages") or {}).get("value") or []
        urls = [p.get("url") for p in pages if p.get("url", "").lower().endswith(".pdf")]
        logger.info("[bing] Query %r → %d PDF URLs", query, len(urls))
        return urls[:max_results]
```

- [ ] **Step 3: Write tests**

```python
# tests/unit/test_bing_search_adapter.py
from unittest.mock import MagicMock, patch
from api.adapters.bing_search_adapter import BingSearchAdapter, BingSearchConfig


def _mk(api_key="k"):
    return BingSearchAdapter(BingSearchConfig(
        endpoint="https://api.bing.microsoft.com/v7.0/search",
        api_key=api_key,
    ))


def test_empty_when_not_configured():
    a = BingSearchAdapter(BingSearchConfig(endpoint="", api_key=None))
    assert a.search_pdfs("anything") == []
    assert not a.is_configured()


def test_extracts_pdf_urls_from_response():
    with patch("requests.get") as get:
        get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"webPages": {"value": [
                {"url": "https://x.com/ar.pdf"},
                {"url": "https://x.com/page.html"},  # non-PDF, filtered out
                {"url": "https://y.com/report.PDF"},  # case-insensitive match
            ]}},
        )
        get.return_value.raise_for_status = lambda: None
        assert _mk().search_pdfs("test") == [
            "https://x.com/ar.pdf",
            "https://y.com/report.PDF",
        ]


def test_swallows_network_error():
    with patch("requests.get", side_effect=ConnectionError("boom")):
        assert _mk().search_pdfs("test") == []
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_bing_search_adapter.py -v
```

Expected: 3 pass.

- [ ] **Step 5: Commit**

```bash
git add api/ports/driven/web_search_port.py api/adapters/bing_search_adapter.py \
        tests/unit/test_bing_search_adapter.py
git commit -m "feat(search): Bing Web Search port + adapter"
```

### Task 2.3 — Wire Bing into discovery flow

**Files:**
- Modify: `api/container.py` (register port → adapter)
- Modify: `api/main.py` (config wiring)
- Modify: `api/services/pdf_web.py` (replace `_search_all_annual_pdfs` DDG call with port)
- Modify: `.github/workflows/deploy.yml` (add `BING_SEARCH_API_KEY` env var)

- [ ] **Step 1: Register in container**

```python
# api/container.py
from api.adapters.bing_search_adapter import BingSearchAdapter, BingSearchConfig
from api.ports.driven.web_search_port import WebSearchPort

def configure(self, config: AppConfig) -> None:
    # ... existing ...
    self._container.register(
        WebSearchPort,
        instance=BingSearchAdapter(config.bing_search),
    )
```

- [ ] **Step 2: Add Config + main.py wiring**

```python
# api/main.py — in the configure_di_container function
from api.adapters.bing_search_adapter import BingSearchConfig

config = AppConfig(
    # ... existing ...
    bing_search=BingSearchConfig(
        endpoint=os.getenv("BING_SEARCH_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search"),
        api_key=os.getenv("BING_SEARCH_API_KEY"),
    ),
)
```

- [ ] **Step 3: Replace DDG call in `pdf_web.py`**

Change `_search_all_annual_pdfs` so it tries Bing first, falls back to DDG:

```python
def _search_all_annual_pdfs(navn: str, hjemmeside: Optional[str]) -> List[str]:
    from api.container import get_container
    from api.ports.driven.web_search_port import WebSearchPort

    try:
        bing = get_container().resolve(WebSearchPort)
        if bing.is_configured():
            queries = []
            if hjemmeside:
                domain = re.sub(r"^https?://", "", hjemmeside).rstrip("/").split("/")[0]
                queries.append(f'site:{domain} "annual report"')
            queries.append(f'{navn} "annual report"')
            urls: List[str] = []
            for q in queries:
                urls += bing.search_pdfs(q, max_results=PDF_URL_LIMIT)
                urls = list(dict.fromkeys(urls))
                if len(urls) >= PDF_URL_LIMIT:
                    break
            if urls:
                return urls[:PDF_URL_LIMIT]
    except Exception as exc:
        logger.warning("[search] Bing failed, falling back to DDG: %s", exc)

    # DDG fallback — kept as last resort for when Bing quota is exhausted
    # or the port isn't configured (local dev). DDG is known-flaky; see the
    # 2026-04-22 harness run showing 0/20 recall from bot detection.
    return _ddg_fallback_search(navn, hjemmeside)


def _ddg_fallback_search(navn: str, hjemmeside: Optional[str]) -> List[str]:
    # ... existing body of _search_all_annual_pdfs moved here ...
```

- [ ] **Step 4: Add secret to deploy.yml ENV_VARS array**

```yaml
"BING_SEARCH_API_KEY=${{ secrets.BING_SEARCH_API_KEY }}"
```

- [ ] **Step 5: Run unit suite**

```bash
uv run pytest tests/unit -q
```

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "feat(search): route discovery through Bing with DDG fallback"
```

### Task 2.4 — Ship Phase 2 + measure

- [ ] **Step 1: PR targeting staging, merge, promote to main.**

- [ ] **Step 2: Re-run the harness** (same `/tmp/run_b4_harness.sh`, updated to include a `bing` arm that hits the port directly).

Record the new recall in a short addendum to the decision doc. Expected: 10–13/20.

---

## Phase 3 — Re-introduce Claude with native `web_search_20250305` tool

Claude's native web_search is the only first-party web search in the fallback chain (Bing is also first-party but it's a search-only API, not an agent). Adding Claude as the top fallback before Azure should push recall to 14–17/20.

### Task 3.1 — Restore `_agent_discover_pdfs_claude`

**Files:**
- Modify: `api/services/pdf_agents.py` (re-add the Claude agent)
- Modify: `tests/unit/test_pdf_agents.py` (re-add Claude tests)

- [ ] **Step 1: Look up the pre-deletion Claude code in git history**

```bash
git log --all --oneline -- api/services/pdf_agents.py | head -10
# Find the commit BEFORE Phase 1's deletion; we'll cherry-pick its Claude function
git show <that-commit>:api/services/pdf_agents.py | sed -n '/^def _agent_discover_pdfs_claude/,/^def /p'
```

- [ ] **Step 2: Add the Claude agent back**

Paste the function into `api/services/pdf_agents.py`, then insert it at the TOP of the `_agent_discover_pdfs` orchestrator's fallback chain (before Azure OpenAI). Also re-add `import anthropic` and the `_parse_agent_pdf_list` helper if it was removed.

- [ ] **Step 3: Tests**

Same pattern as the tests that were deleted in Phase 1 — 5–6 tests covering success, tool-use loop, quota error, homepage fallback.

- [ ] **Step 4: Re-add `ANTHROPIC_API_KEY`** to deploy.yml ENV_VARS array.

- [ ] **Step 5: Add the GitHub secret** (`gh secret set ANTHROPIC_API_KEY` — paste new key value).

- [ ] **Step 6: Run tests + commit**

```bash
uv run pytest tests/unit -q
git add api/services/pdf_agents.py tests/unit/test_pdf_agents.py .github/workflows/deploy.yml
git commit -m "feat(pdf_agents): re-add Claude agent with native web_search tool"
```

### Task 3.2 — Ship Phase 3 + measure

- [ ] **Step 1: PR → staging → promote.**

- [ ] **Step 2: Re-run harness with all 4 arms** (Claude, Azure, Gemini-Vertex, Bing). Expected combined: 14–17/20.

---

## Phase 4 — Expand `PDF_SEED_DATA`

Belt-and-braces: even with great search, for demo / high-traffic companies we pre-seed URLs so discovery is zero-latency and zero-cost.

### Task 4.1 — Curate the top-20 Norwegian companies

**Files:**
- Modify: `api/constants.py` (extend `PDF_SEED_DATA`)

- [ ] **Step 1: Pick companies**

Target list (drawn from brokers' actual top traffic + the recall corpus):

- Telenor ASA (916862037)
- Schibsted ASA (933192410)
- Orkla ASA (930357618)
- Yara International ASA (999001369)
- Kongsberg Gruppen ASA (947990982)
- Storebrand ASA (996525450)
- Aker BP ASA (913540538)
- Tomra Systems ASA (937681140)
- Grieg Seafood ASA (930860675)
- Veidekke ASA (956936264)
- Multiconsult ASA (958935096)
- NEL ASA (934382404)
- NRC Group ASA (981211524)
- Kvaerner ASA (963936060)
- REC Silicon ASA (970921093)
- Glommen Mjøsen Skog SA (986470668)
- Borgestad ASA (975800761)

(Skip DNB / Gjensidige / Søderberg / Equinor — already seeded.)

- [ ] **Step 2: For each company, manually find 2024 annual report URL**

Open IR page in browser → find the 2024 PDF → verify it downloads. Record URL + ~1 sentence label.

This is the longest single task (manual, ~1–2 min per company). 17 companies × 90s = 25 min total.

- [ ] **Step 3: Add to `PDF_SEED_DATA`**

```python
# api/constants.py
PDF_SEED_DATA = [
    # ... existing 4 ...
    {
        "orgnr": "916862037",
        "navn": "Telenor ASA",
        "year": 2024,
        "pdf_url": "https://www.telenor.com/...",  # filled in step 2
        "label": "Telenor Annual Report 2024",
    },
    # ... 16 more ...
]
```

- [ ] **Step 4: Verify seed loads on startup**

```bash
bash scripts/run_api.sh
# Check logs for "seeded N PDF sources" — expect to see the new rows
```

- [ ] **Step 5: Commit + PR**

```bash
git add api/constants.py
git commit -m "feat(seed): add top-17 Norwegian companies to PDF_SEED_DATA"
```

### Task 4.2 — Ship Phase 4 + final measurement

- [ ] **Step 1: Merge via staging, promote to main.**

- [ ] **Step 2: Re-run harness one last time.** Expected: 18–20/20 on a fresh corpus (not the seeded 17 — use 20 DIFFERENT companies for an honest measurement).

- [ ] **Step 3: Update the decision doc** with final numbers. Close the B4 plan.

---

## No placeholders

Every step contains concrete file paths, real code, real commands. No "TBD" / "add appropriate error handling" / "fill in later". The one exception — Task 4.1 Step 2 (finding URLs) — is irreducibly manual; that's stated explicitly.

## Self-review

1. **Spec coverage:** All three user-requested paths covered (Bing = Phase 2, Claude web_search = Phase 3, seed data = Phase 4). Option B cleanup (Phase 1) is a prerequisite enabler.
2. **Placeholder scan:** Clean — every code block is concrete.
3. **Type consistency:** `WebSearchPort.search_pdfs()` returns `List[str]` throughout; `BingSearchConfig` fields match the adapter's constructor signature.
4. **Phase independence:** After Phase 1 lands, Phases 2/3/4 can ship in any order. No cross-phase ordering dependencies beyond Phase 1's cleanup.

## Execution handoff

**"Plan complete. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task (per phase), review between tasks, fast iteration. Best when the user wants hands-off progress.

**2. Inline Execution** — Execute tasks in this session using superpowers:executing-plans, batch execution with checkpoints for user review.

**Which approach?"**

## Out of scope

- Moving off the current Foundry deployment for the Azure OpenAI agent — the deployment is fine; only the agent's prompt/tools are weak.
- Swapping DDG for Serper/SerpAPI instead of Bing — Serper costs $5/mo flat but the free tier on Bing already covers our expected volume (1K queries/month vs our ~100–300 discovery calls/month). If volume grows, Serper becomes cheaper.
- Building a custom search (e.g. crawling BRREG + IR-page heuristics directly). Too large; Bing+seed covers the 80% case.
- Migrating `PDF_SEED_DATA` to a database table. Constants are fine at current size; revisit when it exceeds ~100 entries.
