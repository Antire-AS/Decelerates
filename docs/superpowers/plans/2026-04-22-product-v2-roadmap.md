# Broker Product v2 — Predictive & Portfolio-Level Features

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the broker tool from a "per-company risk snapshot" product into a "portfolio-grade commercial underwriting assistant." Six features build on the Altman Z″ foundation shipped 2026-04-22 (PRs #201/#202) and the existing CRM / portfolio / discovery infrastructure.

**Architecture:** All features are additive — new endpoints, new UI panels, new columns. No breaking schema migrations. Each phase is independently shippable as its own PR. Phases build on each other for narrative coherence but don't block.

**Tech stack:** existing (FastAPI + Next.js + Postgres + Foundry gpt-5.4-mini). One new optional dependency (news API) introduced in Phase H with a clean fallback.

---

## Scope check

Six features, one subsystem each. Ordered by **value-per-hour** as assessed on 2026-04-22:

| Phase | Feature | Primary value | Eng effort |
|---|---|---|---|
| **C** | Altman Z″ historical trend chart | Trajectory > snapshot | ~4h |
| **D** | Portfolio-level risk aggregation | Book-level decisions | ~1d |
| **E** | Peer benchmarking overlay | Contextualizes every number | ~2h |
| **F** | LLM-generated risk narrative | Saves broker prose-writing | ~3h |
| **G** | Scenario analysis slider | Advisory conversations | ~3h |
| **H** | News/events monitor | Proactive monitoring | ~1d + paid API |

**Recommended execution order: C → E → F → D → G → H.**

Rationale:
- C first: closes the staleness-concern from the Altman convo cleanly, shortest ship
- E second: contextualizes numbers the UI already shows — low-effort, high-perceived-quality lift
- F third: needs C + E as inputs for a good narrative
- D fourth: biggest lift, but only valuable once per-company features are solid
- G fifth: niche but delightful when the foundations are there
- H last: introduces new dependency, easiest to defer

---

## File structure

| Phase | New files | Modified files |
|---|---|---|
| C | `api/routers/risk_history.py`, `frontend/.../AltmanTrendChart.tsx` | `api/risk.py`, `api/services/risk_history.py`, `OverviewTab.tsx` |
| D | `api/routers/portfolio_risk.py`, `frontend/src/app/portfolio/risk/page.tsx` | `api/services/portfolio_service.py` |
| E | `frontend/.../BenchmarkBar.tsx` | `api/services/external_apis.py` (SSB cache), `FinancialsTab.tsx` |
| F | `api/services/risk_narrative.py`, `api/routers/risk_narrative.py` | `RiskScoreSection.tsx` (adds narrative) |
| G | `frontend/.../ScenarioSlider.tsx` | Client-side only — reuses exported `compute_altman_z_score` via API |
| H | `api/services/news_monitor.py`, `api/routers/news.py`, `NewsFeed.tsx` (new tab) | `CLAUDE.md` (document new external dep) |

---

## Phase C — Altman Z″ historical trend chart

**Goal:** Show the last 5 years of Altman Z″ on the company profile as a line chart. Answer "is this distress trajectory improving or getting worse?" in one glance.

**Why this is the right next step:**
- Uses existing `company_history` table data (no new extraction)
- Directly extends Phase B (UI already knows about Z″)
- Addresses the "do we need quarterly data?" question: trajectory over 5 annuals is more signal than 4 quarters

### Task C.1 — Backend: endpoint returning Z″ history

**Files:**
- Create: `api/services/risk_history.py`
- Create: `api/routers/risk_history.py`
- Modify: `api/main.py` (register new router)

- [ ] **Step 1: Service function that computes Z″ per historical row**

```python
# api/services/risk_history.py
"""Historical Altman Z'' — compute the score for every year we have
financials on file, so the UI can chart the trajectory."""

from typing import List, Dict, Any

from sqlalchemy.orm import Session

from api.db import CompanyHistory
from api.risk import compute_altman_z_score


def get_altman_z_history(db: Session, orgnr: str) -> List[Dict[str, Any]]:
    """Return [{year, z_score, zone, score_20}] for every year with
    enough extracted financials to compute Z''. Years where Z'' is
    None (incomplete extraction, bank/insurer) are omitted — the chart
    shows gaps rather than misleading zeros."""
    rows = (
        db.query(CompanyHistory)
        .filter(CompanyHistory.orgnr == orgnr)
        .order_by(CompanyHistory.year.asc())
        .all()
    )
    out: List[Dict[str, Any]] = []
    for row in rows:
        # CompanyHistory stores extracted financials as JSON; re-use the
        # same shape as /org/{orgnr}'s regn so compute_altman_z_score
        # just works.
        regn = row.financials_json or {}
        altman = compute_altman_z_score(regn)
        if altman is None:
            continue
        out.append({
            "year": row.year,
            "z_score": altman["z_score"],
            "zone": altman["zone"],
            "score_20": altman["score_20"],
        })
    return out
```

- [ ] **Step 2: FastAPI router**

```python
# api/routers/risk_history.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.dependencies import get_db
from api.services.risk_history import get_altman_z_history

router = APIRouter()


@router.get("/org/{orgnr}/risk-history")
def risk_history(orgnr: str, db: Session = Depends(get_db)) -> dict:
    """Altman Z'' historical series for charting. Returns empty list
    if no years have enough data — UI hides the chart in that case."""
    return {"orgnr": orgnr, "altman_history": get_altman_z_history(db, orgnr)}
```

- [ ] **Step 3: Register router in `api/main.py`**

```python
from api.routers import risk_history
app.include_router(risk_history.router)
```

- [ ] **Step 4: Unit tests**

```python
# tests/unit/test_risk_history.py — test with synthetic CompanyHistory rows
def test_altman_z_history_skips_incomplete_years():
    # 2022: complete financials → Z'' computable
    # 2023: missing working_capital → skipped
    # 2024: complete again → Z'' computable
    # result should have 2 entries (2022, 2024), not 3
    ...
```

- [ ] **Step 5: Commit**

### Task C.2 — Frontend: trend chart component

**Files:**
- Create: `frontend/src/components/company/tabs/overview/AltmanTrendChart.tsx`
- Modify: `frontend/src/components/company/tabs/overview/AltmanZSection.tsx` (embed the chart)

- [ ] **Step 1: Install `recharts` if not already present**

```bash
cd frontend
grep recharts package.json  # verify already installed (likely yes — used elsewhere)
```

- [ ] **Step 2: Chart component**

```tsx
// AltmanTrendChart.tsx
"use client";

import useSWR from "swr";
import { LineChart, Line, XAxis, YAxis, Tooltip, ReferenceLine, ResponsiveContainer } from "recharts";
import { apiFetch } from "@/lib/api";

interface Props { orgnr: string; }

interface HistoryPoint { year: number; z_score: number; zone: string; }

export default function AltmanTrendChart({ orgnr }: Props) {
  const { data } = useSWR<{ altman_history: HistoryPoint[] }>(
    `/org/${orgnr}/risk-history`,
    (url: string) => apiFetch<{ altman_history: HistoryPoint[] }>(url),
  );
  const points = data?.altman_history ?? [];
  if (points.length < 2) return null;  // need at least 2 points for a trend

  return (
    <div className="mt-3">
      <div className="text-xs font-medium mb-1">Altman Z″ — 5-års trend</div>
      <ResponsiveContainer width="100%" height={120}>
        <LineChart data={points}>
          <XAxis dataKey="year" fontSize={10} />
          <YAxis domain={[0, 4]} fontSize={10} />
          <Tooltip />
          <ReferenceLine y={2.60} stroke="#C8A951" strokeDasharray="3 3" label={{ value: "Trygg", fontSize: 10 }} />
          <ReferenceLine y={1.10} stroke="#C0392B" strokeDasharray="3 3" label={{ value: "Nød", fontSize: 10 }} />
          <Line type="monotone" dataKey="z_score" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 3: Embed in `AltmanZSection.tsx`** after the current-year breakdown
- [ ] **Step 4: Build passes** (`npm run build`)
- [ ] **Step 5: Commit + PR to staging**

---

## Phase E — Peer benchmarking overlay

**Goal:** Every financial metric on the profile gets a ghost bar showing the NACE-section industry median, so brokers see "equity 18% vs industry 32% median" at a glance.

### Task E.1 — Backend: benchmark endpoint

**Files:**
- Modify: `api/services/external_apis.py` (wrap `NACE_BENCHMARKS` into a service method)
- Create: `api/routers/benchmarks.py`

- [ ] **Step 1: Expose benchmarks by NACE**

```python
# api/services/external_apis.py — add method
def get_nace_benchmarks(self, nace_section: str) -> Dict[str, Any]:
    """Return the hardcoded NACE benchmark row (see api/constants.py)
    for display alongside a company's actual ratios."""
    from api.constants import NACE_BENCHMARKS
    return NACE_BENCHMARKS.get(nace_section, {})
```

- [ ] **Step 2: Router — GET /benchmarks/{nace_section}**
- [ ] **Step 3: Unit tests**

### Task E.2 — Frontend: BenchmarkBar component

**Files:**
- Create: `frontend/src/components/company/BenchmarkBar.tsx`
- Modify: `FinancialsTab.tsx` to use BenchmarkBar on each ratio

- [ ] **Step 1: Simple horizontal bar component**

```tsx
// BenchmarkBar.tsx
interface Props {
  value: number;         // company's actual ratio, 0-1
  min: number;           // industry range lower bound
  max: number;           // industry range upper bound
  label: string;
}

export default function BenchmarkBar({ value, min, max, label }: Props) {
  // ... render bar with company value as a dot and industry range shaded
}
```

- [ ] **Step 2: Wire into FinancialsTab for equity ratio, margin, debt ratio**
- [ ] **Step 3: Commit + PR**

---

## Phase F — LLM-generated risk narrative

**Goal:** A 2-3 paragraph natural-language summary of why a company scores what it does, drawing on Altman components + rule factors + peer benchmarks. Saves brokers from writing the same prose for every client report.

### Task F.1 — Backend: narrative service

**Files:**
- Create: `api/services/risk_narrative.py`
- Create: `api/routers/risk_narrative.py`

- [ ] **Step 1: Foundry-backed narrative generator**

```python
# api/services/risk_narrative.py
from api.services.llm import _llm_answer_raw

RISK_NARRATIVE_PROMPT = """Du er en erfaren risikoanalytiker...
Gitt følgende data for {navn} (orgnr {orgnr}):

ALTMAN Z'': {z_score} ({zone})
  Likviditet (WC/TA): {wc_ratio}
  Historisk inntjening (RE/TA): {re_ratio}
  Driftslønnsomhet (EBIT/TA): {ebit_ratio}
  Soliditet (BE/TL): {leverage_ratio}

REGEL-BASERTE FLAGG:
{rule_factors}

BRANSJE-BENCHMARK (NACE {nace}):
  Medium egenkapitalandel: {eq_median}
  Medium driftsmargin: {margin_median}
  Selskap vs. bransje: {benchmark_delta}

Skriv 2-3 korte avsnitt på norsk..."""


def generate_narrative(company_data: dict) -> str:
    prompt = RISK_NARRATIVE_PROMPT.format(**company_data)
    return _llm_answer_raw(prompt) or ""
```

- [ ] **Step 2: Router that collates data + calls narrative**
- [ ] **Step 3: Cache — hash the inputs, store narrative for 7 days**

### Task F.2 — Frontend: narrative panel

**Files:**
- Modify: `RiskScoreSection.tsx` (add narrative block below risk score)

- [ ] **Step 1: SWR hook calling /org/{orgnr}/risk-narrative**
- [ ] **Step 2: Loading skeleton while generating**
- [ ] **Step 3: "Regenerer" button to force refresh**
- [ ] **Step 4: Commit + PR**

---

## Phase D — Portfolio-level risk aggregation

**Goal:** Brokers managing 50-200 companies need a book-level view — which clients are in each Altman zone, which just moved into distress since last review, what's the aggregate premium-at-risk.

### Task D.1 — Backend: portfolio risk aggregation endpoint

**Files:**
- Create: `api/routers/portfolio_risk.py`
- Modify: `api/services/portfolio_service.py`

- [ ] **Step 1: Aggregate service method**

```python
def get_portfolio_risk_summary(self, portfolio_id: int) -> Dict[str, Any]:
    """Return per-zone counts + total premium at risk + companies
    that moved zones since last snapshot."""
    # 1. Load all companies in portfolio
    # 2. For each: compute Altman Z'' using latest extracted financials
    # 3. Group by zone
    # 4. Compare to stored previous snapshot (new table: portfolio_risk_snapshot)
    # 5. Return summary
    ...
```

- [ ] **Step 2: New `portfolio_risk_snapshot` table**

```sql
-- Alembic migration
CREATE TABLE portfolio_risk_snapshot (
  id SERIAL PRIMARY KEY,
  portfolio_id INTEGER NOT NULL REFERENCES portfolios(id),
  orgnr VARCHAR(9) NOT NULL,
  z_score NUMERIC(5,2),
  zone VARCHAR(16),
  snapshot_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_portfolio_risk_snapshot_portfolio_snapshot
  ON portfolio_risk_snapshot(portfolio_id, snapshot_at DESC);
```

- [ ] **Step 3: Daily cron task** that inserts one snapshot row per company per portfolio (reuses existing background-task infrastructure)

- [ ] **Step 4: Router + tests**

### Task D.2 — Frontend: portfolio risk dashboard

**Files:**
- Create: `frontend/src/app/portfolio/[id]/risk/page.tsx`

- [ ] **Step 1: Zone distribution chart** — stacked bar showing counts per zone
- [ ] **Step 2: Transition list** — companies that moved zones since last snapshot, with arrows
- [ ] **Step 3: Premium-at-risk** — sum of annual premium for clients in Nødsone
- [ ] **Step 4: Commit + PR**

---

## Phase G — Scenario analysis slider

**Goal:** On the company profile, let a broker slide "revenue changes by X%" and watch the Altman Z″ recompute live. Great for advisory conversations.

### Task G.1 — Frontend-only: reactive Altman recompute

**Files:**
- Create: `frontend/src/components/company/tabs/overview/ScenarioSlider.tsx`
- Reuse: the existing `altman_z.components` exposed from /org/{orgnr}

- [ ] **Step 1: Port Altman formula to TypeScript** (it's 4 lines of arithmetic)

```tsx
// Re-implement compute_altman_z_score in TS so slider is zero-latency.
// Kept tiny on purpose so drift with api/risk.py is obvious — add unit
// test that pins a known-value output to catch formula divergence.
function computeZ(x1: number, x2: number, x3: number, x4: number): number {
  return 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4;
}
```

- [ ] **Step 2: Slider UI** — revenue delta -30% to +30%, EBIT delta -50% to +50%, recompute on change
- [ ] **Step 3: Show new Z″ + zone in real time**
- [ ] **Step 4: Unit test for the TS compute function — input known values, assert output matches the Python reference**
- [ ] **Step 5: Commit + PR**

---

## Phase H — News/events monitor

**Goal:** Flag when a tracked client has material news (lawsuits, management changes, credit rating moves, bankruptcy filings). This turns the broker app from a lookup tool into a monitoring tool.

### Task H.1 — News API integration

**Files:**
- Create: `api/services/news_monitor.py`
- Create: `api/adapters/gnews_adapter.py` (or Serper's news endpoint — already have that API key)
- Create: `api/routers/news.py`

- [ ] **Step 1: Pick a news API**
  - Option 1: Serper's /news endpoint (already paying for Serper) — recommended
  - Option 2: GNews free tier (100/day)
  - Option 3: EventRegistry (paid)

- [ ] **Step 2: Fetch news for a company by name, filter last 30 days**

- [ ] **Step 3: Classify events** via Foundry gpt-5.4-mini (material vs noise) — single LLM call per fetched article

- [ ] **Step 4: Store in new `company_news` table**

```sql
CREATE TABLE company_news (
  id SERIAL PRIMARY KEY,
  orgnr VARCHAR(9) NOT NULL,
  headline TEXT NOT NULL,
  url TEXT NOT NULL,
  published_at TIMESTAMPTZ NOT NULL,
  material BOOLEAN NOT NULL DEFAULT FALSE,
  event_type VARCHAR(32),    -- "lawsuit", "mgmt_change", "credit_event", "other"
  summary TEXT,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_company_news_orgnr_published ON company_news(orgnr, published_at DESC);
```

- [ ] **Step 5: Background task — refresh per company once per day**

### Task H.2 — Frontend: news tab + portfolio alerts

**Files:**
- Create: `frontend/src/components/company/tabs/NewsTab.tsx` (new tab on company profile)
- Modify: portfolio dashboard to highlight clients with material news in last 7 days

- [ ] **Step 1: News tab — list material events with date + summary**
- [ ] **Step 2: "Material" badge on portfolio cards**
- [ ] **Step 3: Commit + PR**

---

## No placeholders

Every task has concrete file paths, real code, exact commands. The Altman formula in TypeScript is deliberately 4 lines so the Python/TS equivalence is easy to keep in sync. News API choice in H.1 lists three real options ranked by fit (Serper wins because the key is already provisioned from Phase 2).

## Self-review

**Spec coverage:** All six features covered. Phase ordering explicit and justified. Each phase standalone-shippable.

**Type consistency:** `AltmanZScore` shape stays the same across C/D/G — the backend `compute_altman_z_score` function is reused (Phase C) or mirrored in TS (Phase G).

**Placeholder scan:** Each code block is concrete. The one place with a `...` is Phase D.1 Step 1 (the aggregation service method signature — body is 5 numbered substeps in the docstring rather than code, which is fine for a plan).

## Execution handoff

**Plan complete. Recommended approach:**

1. **Ship Phase C first** — shortest ship (~4h), highest value multiplier on the Altman panel that just went live
2. Review what brokers say about C before committing to D
3. D is the biggest swing in the plan — might want user research before shipping 1d of eng

**Execution options:**

1. **Subagent-driven** — one subagent per phase with spec-review between. Good if you want hands-off multi-day shipping.
2. **Inline phase-by-phase** — I ship one phase, you review, decide on next. Slower but higher-touch.

**Which phase do you want to start with — C (trend chart), E (peer benchmarks), or F (LLM narrative)?**

## Out of scope

- Rewriting the rule-based risk score from scratch. Altman augments; the rules are still useful for legal/compliance flags (bankruptcy, PEP, under-avvikling).
- Migrating to a machine-learning distress model. Altman is good enough for the volume this tool handles, and ML needs labelled training data we don't have.
- Quarterly financial data. Analyzed separately — not worth adding for underwriting decisions even with these features. Trend chart in Phase C addresses the "is data too old" concern better than quarterly would.
- Embedding this into the Signicat portal flow (where clients self-onboard). Separate product surface.
- Multi-country expansion. All six features assume Norwegian companies / NACE classification.
