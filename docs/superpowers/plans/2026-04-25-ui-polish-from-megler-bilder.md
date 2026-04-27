# UI Polish — Drawn From `~/Desktop/megler blider/` Mockups

**Date:** 2026-04-25
**Status:** roadmap (not yet a TDD plan — needs scope-cut before implementation)
**Inspired by:** 20 screenshots saved by Tharusan as inspiration for the broker
UX. He liked the "rød tråd" (continuous thread) of a single, coherent system
rather than 10 individually-styled pages.

---

## What's already in the app

A quick reality check before assuming we need to build everything:

- `frontend/src/components/layout/AppShell.tsx` — sidebar exists, but the
  groupings don't yet match the **ARBEID / SALG / COMPLIANCE / SYSTEM**
  semantic split shown in screenshot 135259.
- `frontend/src/components/a11y/a11y-panel.tsx` — Tilgjengelighet menu exists
  with font scale + reduced motion + high contrast. **Font scale was broken
  until PR #249** (today's hotfix) because the CSS scaled `body` only, not
  `<html>`, so Tailwind utilities ignored it.
- `/dashboard`, `/search`, `/portfolio`, `/renewals`, `/sla`, `/pipeline`,
  `/knowledge`, `/idd`, `/insurers`, `/recommendations`, `/prospecting`,
  `/admin` — all routes exist; the work is presentation polish, not
  net-new pages.

---

## 1 — Bug: a11y options don't customize colors

**Symptom (user-reported 2026-04-24):** "the accessibility options don't work
on the website."

**Two distinct problems hiding under one complaint:**

| Sub-issue | Status |
|---|---|
| Font-scale slider visually does nothing | **Fixed** in PR #249 (move scaling from `body` to `<html>`) |
| No color-theme picker (user mentioned "fontene, fargetonene") | **Not started** — the menu has "Høy kontrast" boolean only; no palette picker |

**Proposed expansion:**
Add a `Tema` radio group to `A11yPanel` next to the existing `Skriftstørrelse`
radio group. Options:
- `system` (default — follows OS prefers-color-scheme)
- `lys` (force light)
- `mørk` (force dark)
- `varm` (warm sepia, easier on long reads — sets `--background` to a faint
  cream and `--foreground` to deep brown via `[data-theme="warm"]` selector)
- `kontrast` (the existing "Høy kontrast" promoted from a checkbox to a theme
  variant — declutters the menu)

The persistence + `<html>` data-attribute pattern in `a11y-provider.tsx`
already handles this; we'd add `theme: ThemeKey` alongside the existing
state and a matching `[data-theme]` block in `globals.css`.

**Cost:** ~1 hour. **Value:** addresses the user's actual mental model.

---

## 2 — Sidebar consolidation (135259)

**Today:** flat list of menu items in `AppShell.tsx`.

**Mockup:** four labelled sections —

```
ARBEID         SALG              COMPLIANCE          SYSTEM
  Hjem           Prospektering    IDD / Behov         Kunnskapsbase
  Selskapsøk     Fornyelser       Forsikringsselskap  Admin
  Pipeline       Anbud            Avtaler
  Portefølje
```

**Why it matters:** the sidebar is currently 14 items in one undifferentiated
column. Grouping by lifecycle (find work → sell → audit → admin) is the
"rød tråd" the user wants.

**Implementation:** add a `section` field to each `NavItem` and render a small
muted `<h3>` between groups in `AppShell`. No new routes, no logic changes.

**Cost:** ~30 min. **Value:** every page benefits because it's the universal
chrome.

---

## 3 — Dashboard hurtighandlinger + activity feed (135111)

**Mockup:** four-quadrant landing page —

| Top-left | Top-right |
|---|---|
| **Samlet premievolum** — bar chart 12-month trend, big number with YoY delta | **Forfaller snart** — top 3 contracts with countdown days |
| **Siste aktiviteter** — call/email/note feed with "Åpen" badge | **Hurtighandlinger** — Søk selskap (⌘K), Ny behovsanalyse, Generer anbudspakke, Vis portefølje |

**Why it matters:** the current `/dashboard` is metrics-first; brokers want
"what's the next thing I should do" first. Hurtighandlinger gives one-click
entry into the most common workflows.

**Backing data:**
- Samlet premievolum: aggregate of `insurance_offers.premium` grouped by month
- Forfaller snart: query `insurance_documents` where `expires_at < now+60d`
- Siste aktiviteter: read from `broker_notes` joined with company/note kind

**Cost:** ~1 day backend (3 new aggregation endpoints) + 1 day frontend.

---

## 4 — Selskapsøk risk-bucket filter chips (135135)

**Mockup:** above the results table, 4 filter chips — `Alle`, `Lav risiko`,
`Middels`, `Høy risiko`. Each row shows a colored risk badge inline.

**Today:** `/search` returns BRREG results without any client-side risk filter.

**Implementation:** the risk score already exists per Company (`risk_score`
column). Add chips that filter the local results list; the badge per row uses
the same `RISK_BANDS` source-of-truth in `api/risk.py` exposed via
`GET /risk/config`.

**Cost:** ~3 hours. **Value:** brokers triage by risk first when prospecting.

---

## 5 — Pipeline kanban polish (135146)

**Today:** `/pipeline` already exists with drag-and-drop. The mockup confirms
the design pattern but adds two header metrics:
- `kr 12.0 mill samlet verdi` (sum of all deals)
- `kr 8.7 mill vektet` (sum-product of deal value × probability%)

Each card shows percentage + a progress bar matching the probability.

**Cost:** ~2 hours. The kanban board is the right shape; just add the two
header summaries and the per-card progress bar.

---

## 6 — Tender-detail tab structure (134xxx earlier batch)

The mockups show **6 tabs** on the company profile:
`Oversikt | Økonomi | Forsikring | CRM | Fokus | Nyheter`

**Today:** `/search/[orgnr]` has 6 tabs but they are
`oversikt | økonomi | forsikring | crm | notater | chat`.

**Differences:**
- `Fokus` (mockup) vs `notater` (today) — Fokus is a curated "what to act on
  next" view; today's Notater is a flat note list.
- `Nyheter` (mockup) vs `chat` (today) — Nyheter would surface news events
  for the company (uses the `news_service` shipped in PR #216).

**Recommendation:** keep `notater` and `chat` (existing functionality) but
**add** `Fokus` and `Nyheter` as two new tabs. Don't replace working features.

**Cost:** Fokus = ~half day (renders top-N action items derived from notes +
upcoming renewals + risk reasons). Nyheter = ~half day (consume news_service
output that's already there from PR #216).

---

## 7 — Step-tracker on tender flow (earlier batch)

User flagged this in the original list ("Step-tracker"). The pattern: 5-step
horizontal indicator at the top of `/tenders/[id]` showing progress through
`Behovsanalyse → Anbudspakke → Sendt → Mottatt → Sammenligning`.

**UX rule from CLAUDE.md:** "Don't put numbers in workflow circles — use ✓
for completed, ● for active, ○ for upcoming." This is non-negotiable: the
F07/F19 audit flagged it.

**Cost:** ~3 hours.

---

## 8 — AI-sammendrag with highlighting (earlier batch)

**Today:** the chat tab can answer questions but there's no canonical
"summary" surface that highlights the source quote.

**Mockup pattern:** a paragraph of AI-generated summary at the top of
`Oversikt` with citation markers `[1] [2]` that highlight the matching
sentence in the source PDF when hovered.

**Cost:** non-trivial — needs RAG-citation plumbing. Defer until users ask
for it. Note in roadmap; don't build yet.

---

## 9 — Tilbudssammenligning side-by-side (earlier batch)

**Today:** `/tenders/[id]/compare` exists (PR history confirms) but the
visual is plain text.

**Mockup pattern:** 3-column table with the broker's recommendation
highlighted in the first column, and per-row green/red diff coloring on
sums (premium, deductible, coverage limits).

**Cost:** ~half day.

---

## 10 — Forsikringsselskaper admin row (mockup batch)

The mockup shows an admin table for managing insurer contacts (name, email,
last contact, response time). Today there's `/insurers` but it's read-only.

**Cost:** ~half day to add CRUD.

---

## Suggested execution order

| Order | Item | Effort | Why first |
|---|---|---|---|
| 1 | Color theme picker (Section 1) | 1 h | User explicitly asked, complements the font fix that just shipped |
| 2 | Sidebar consolidation (Section 2) | 30 min | Universal chrome — every other change benefits |
| 3 | Selskapsøk filter chips (Section 4) | 3 h | Quick win, highest-traffic page |
| 4 | Pipeline header metrics (Section 5) | 2 h | Existing page, two-card addition |
| 5 | Step-tracker on tender flow (Section 7) | 3 h | Helps the demo flow that just got hardened |
| 6 | Dashboard quadrants (Section 3) | 2 d | Bigger build, but most-visible "first impression" |
| 7 | Fokus + Nyheter tabs (Section 6) | 1 d | Builds on existing tab structure |
| 8 | Tilbudssammenligning visual (Section 9) | half day | Demo-flow polish |
| 9 | Forsikringsselskaper CRUD (Section 10) | half day | Operational, not customer-facing |
| 10 | AI-sammendrag with citations (Section 8) | deferred | Defer until user asks |

Total for items 1–9: roughly **5 development days** if executed sequentially,
~3 days if some are parallelised across separate small PRs.

---

## What this plan is NOT

- It is **not** a full TDD plan ready for `subagent-driven-development` — each
  numbered item needs its own bite-sized plan before implementation. The
  intention here is a roadmap to align on, not a build script.
- It does **not** propose a redesign of the design system. Tailwind + shadcn
  stays; we're using the existing primitives and matching the mockup look
  with class composition.
- It does **not** replace working features. Wherever the mockup conflicts
  with shipped behaviour, the shipped behaviour wins until evidence says
  otherwise.
