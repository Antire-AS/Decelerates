# Frontend Usability Audit — Design Spec

**Date**: 2026-04-17
**Author**: Tharusan + Claude (audit pass)
**Status**: Design approved, plan pending
**Predecessor**: [`docs/ui-audit-2026-04-09.md`](../../ui-audit-2026-04-09.md) (F01–F19)

---

## 1. Background and goal

The 2026-04-09 audit (F01–F19) closed the loudest functional bugs on staging
but stopped short of a systematic usability pass. Since then the frontend
has grown: 20 routes, an OnboardingTour, multi-provider OAuth, and a 6-tab
company profile. This spec captures a complete usability sweep across all
20 routes against:

- **Nielsen 10 heuristics** (visibility, match with real world, user
  control, consistency, error prevention, recognition, flexibility, minimalism,
  recovery, help)
- **WCAG 2.1 AA basics** (semantic HTML, ARIA, focus-visible, labels,
  keyboard equivalents, color contrast)
- **Task-flow efficiency** (click count, hidden affordances)
- **State coverage** (loading / empty / error for every async path)
- **Visual consistency** (typography scale, spacing, color tokens)
- **Responsive behavior** (especially the public `/portal/[token]`)
- **Norwegian-language consistency**

**Goal**: ship a tiered set of PRs that lifts measurable usability —
WCAG 2.1 AA conformance on the broker workflow, design-system
de-duplication, and the long tail of paper cuts brokers see daily.

**Non-goal**: visual rebrand, new features, login UX rework (currently
bypassed), or backend schema changes.

---

## 2. Audit findings

~50 raw findings across 20 surfaces, consolidated into 20 themed items
(U01–U20) below. The full per-surface output lives in the session
transcript; this section is the planning index.

### Severity index

🔴 Critical · 🟠 High · 🟡 Medium · 🟢 Low

| ID  | Sev | Theme                                                          | Surfaces affected                              | Effort |
|-----|-----|----------------------------------------------------------------|------------------------------------------------|--------|
| U01 | 🟠  | Risk-band thresholds hardcoded, divergent from backend         | search, portfolio, prospecting, portal         | M      |
| U02 | 🟠  | Form `<label>` missing `htmlFor` association                   | dashboard, search, prospecting, tenders, admin | S × N  |
| U03 | 🟠  | No shared Button / Input / Card / Dialog primitives            | all 20 routes                                  | L      |
| U04 | 🟠  | 658+ inline hex codes instead of semantic Tailwind tokens      | all 20 routes                                  | M      |
| U05 | 🟠  | Browser `confirm()` / `alert()` for destructive actions        | pipeline, idd, tenders, admin                  | M      |
| U06 | 🟠  | Pipeline drag-and-drop has no keyboard alternative             | pipeline (renewals kanban shares risk)         | M      |
| U07 | 🟡  | Tab navigation lacks ARIA tabs pattern + focus management      | search/[orgnr] (6 tabs), portfolio/analytics   | M      |
| U08 | 🟡  | No skip-to-content link, no `aria-current` on nav              | AppShell (cascades to every route)             | S      |
| U09 | 🟡  | Global `:focus` instead of `:focus-visible`                    | globals.css + all forms                        | M      |
| U10 | 🟡  | Modals lack focus trap + Escape handler                        | onboarding, prospecting, tenders               | M      |
| U11 | 🟡  | Async fetches without error state UI                           | dashboard, renewals, portfolio analytics       | S × N  |
| U12 | 🟡  | Lazy-loaded tabs missing loading skeletons                     | search/[orgnr] CRM tab                         | S      |
| U13 | 🟡  | No global `loading.tsx` / `not-found.tsx`                      | root                                           | M      |
| U14 | 🟡  | Mobile responsive gaps (table hides cols, no card alternative) | prospecting, portal (narrow `max-w-3xl`)       | M      |
| U14b| 🟢  | Renewals: email/notification controls only in kanban, not table view | renewals                                  | M      |
| U15 | 🟡  | Knowledge chat lacks "stop generating" affordance              | knowledge                                      | M      |
| U16 | 🟡  | SLA wizard: no "unsaved changes" warning on back / refresh     | sla                                            | S      |
| U17 | 🟢  | Per-page metadata missing (browser tab titles)                 | all 20 routes                                  | M      |
| U18 | 🟢  | IDD: no inline form validation hints                           | idd                                            | S      |
| U19 | 🟢  | Insurers form uses `border-gray-200` instead of brand          | insurers                                       | S      |
| U20 | 🟢  | Pipeline shows owner as `User #42`, not name                   | pipeline                                       | M      |

(Lower-severity polish items — pipeline grip aria-label, audit log filter
labels, IDD risk-pill icons, etc. — fold into Tier 4 polish PR.)

### Visual polish (from staging screenshots)

Confirmed by inspecting `staging-dashboard-tour-step-2.png` and
`staging-dnb-profile-oversikt.png`: typography hierarchy is sound,
contrast is solid (no washed-out text), spacing is well-paced. The
DNB profile screenshot predates the F07/F19 fix (still shows numbers
in workflow circles), but `WorkflowStepper.tsx:39` is correct as of
this audit. **No visual debt to address.**

### What is intentionally excluded from this initiative

- **Login screen UX** — currently bypassed by redirect to `/dashboard`;
  revisit when re-enabled.
- **Backend `RISK_BANDS` model** — already correct; the fix is purely
  frontend (consume `GET /risk/config` instead of hardcoding).
- **Mobile prospecting table redesign** — needs a separate design pass
  (card layout vs collapsible rows). Filed as U14, deferred.
- **Pipeline owner name resolution** — needs backend user lookup
  endpoint. Filed as U20, deferred.

---

## 3. Architectural decisions

### D1 · Component primitives — adopt **shadcn/ui**

Build the shared primitive layer using shadcn/ui (Radix primitives +
Tailwind, copy-paste components, no runtime dep). Rationale:

- Radix solves WCAG-correct focus trap, ARIA tabs, dialog, dropdown,
  combobox out of the box — eliminates U07, U08 (partial), U10 by
  construction
- Same Tailwind-driven aesthetic as today; restyles trivially to brand
  palette
- No npm runtime dep — components live in `frontend/src/components/ui/`
  and are owned by us
- Matches the gradient most modern Next.js codebases land on; reduces
  the "what stack is this" cognitive load for any future contributor

**Components to install** (Tier 2): `button`, `input`, `textarea`,
`select`, `card`, `badge`, `dialog`, `tabs`, `tooltip`, `dropdown-menu`,
`alert`, `skeleton`.

### D2 · Risk-band consumption — **SWR hook**

Add `useRiskConfig()` to `frontend/src/lib/api.ts` as an SWR hook with
infinite cache (the bands rarely change). Replace 4 hardcoded sites:

- `frontend/src/components/company/RiskBadge.tsx`
- `frontend/src/components/company/tabs/overview/shared.tsx`
- `frontend/src/app/portfolio/page.tsx` (`_FALLBACK_BANDS`)
- `frontend/src/app/prospecting/page.tsx` (`RISK_BANDS` + `riskColor()`)
- `frontend/src/app/portal/[token]/page.tsx`

Rejected alternatives:
- React Context provider — bigger blast radius, requires layout-level
  wrapping; overkill for one config value
- Server Component fetch + prop drilling — would change the rendering
  model of multiple pages

### D3 · Hex-code migration scope — **primitives + AppShell only**

Tier 2 migrates inline hex codes only inside the new `ui/` primitives
and `components/layout/AppShell.tsx`. The remaining ~600 inline codes
are tagged with a tracking issue and cleaned up gradually as files are
otherwise touched. Big mechanical diffs are review-hostile.

Brand tokens already exist in `globals.css` — Tier 2 verifies completeness
and adds any missing semantic names (e.g. `text-brand-mid`, `border-brand-stone`).

### D4 · Dialog primitive replaces **all** browser `confirm()` / `alert()`

Once `Dialog` lands (Tier 2), Tier 2 also rips out every `confirm()`
and `alert()` call in `pipeline`, `idd`, `tenders`, `admin`. They are
WCAG fails (no focus trap, no Escape handling, native styling) and
trivial to replace once the primitive exists.

### D5 · ARIA tabs pattern — **shadcn `tabs` component**

Tier 3 replaces the bespoke tab implementation in `search/[orgnr]/page.tsx`
and `portfolio/analytics` with shadcn `tabs`, which is a thin wrapper over
Radix and handles `role="tab"`, `aria-selected`, arrow-key navigation,
focus management, and `tabpanel` association.

### D6 · Pipeline keyboard drag — **`@dnd-kit/keyboard` KeyboardSensor**

Tier 3 adds `KeyboardSensor` alongside the existing `PointerSensor`.
Update grip aria-label to mention "Dra med mus eller bruk pil-taster".
Renewals kanban gets the same treatment if it uses dnd-kit (verify in
Tier 3 — currently unaudited at the dnd level).

---

## 4. Implementation plan — 4 PR tiers

Each tier is a single PR (or two if a tier is large). Tiers ship in
order so that later tiers can depend on earlier infrastructure.

### Tier 1 — Quick wins (~1 day, 1 PR)

Lifts immediate a11y + correctness without touching architecture.

| Task                                                       | Severity covered |
|------------------------------------------------------------|------------------|
| Build `useRiskConfig()` SWR hook in `lib/api.ts`           | U01              |
| Replace 5 hardcoded risk-band sites with the hook          | U01              |
| Sweep all `<label>` elements, add `htmlFor` + matching `id`| U02              |
| Add skip-to-content link in `AppShell.tsx`                 | U08              |
| Add `aria-current="page"` to active sidebar link           | U08              |
| Migrate global `:focus` → `:focus-visible` in `globals.css`| U09              |

**Acceptance**:
- `axe-core` scan on `/dashboard`, `/search/[orgnr]`, `/portfolio`
  reports zero `label-htmlFor`-missing and zero `aria-current` warnings.
- `grep -rE "(RISK_BANDS|_FALLBACK_BANDS|riskColor)" frontend/src` returns
  only the new `useRiskConfig()` hook and the fallback constant inside it.
- `globals.css` and component files use `:focus-visible` exclusively for
  interactive-element focus rings; no remaining `focus:ring-` (without
  `-visible`) on buttons or inputs.

### Tier 2 — Foundation (~3–4 days, 1–2 PRs)

Builds the primitive library and rips out all browser dialogs.

| Task                                                       | Severity covered |
|------------------------------------------------------------|------------------|
| `npx shadcn init` configured for project; pick brand palette| U03             |
| Install primitives: button, input, textarea, select, card, badge, dialog, tabs, tooltip, dropdown-menu, alert, skeleton | U03 |
| Wire shadcn primitives to brand tokens in `tailwind.config` and `globals.css` | U04 |
| Replace AppShell inline hex codes with semantic Tailwind tokens | U04 |
| Replace `confirm()` / `alert()` in pipeline, idd, tenders, admin with `Dialog` / `Alert` | U05 |
| File tracking issue for remaining ~600 inline hex codes (gradual cleanup) | U04 |

**Acceptance**: `frontend/src/components/ui/` contains 12+ primitives;
zero remaining `confirm(` or `alert(` calls in `frontend/src/`;
`AppShell.tsx` and all `ui/` primitives use only semantic Tailwind classes
(no inline `[#...]`).

### Tier 3 — Accessibility hard issues (~2–3 days, 1–2 PRs)

| Task                                                       | Severity covered |
|------------------------------------------------------------|------------------|
| Replace bespoke tabs in `search/[orgnr]/page.tsx` with shadcn `tabs` | U07 |
| Replace bespoke tabs in `portfolio/analytics` with shadcn `tabs`     | U07 |
| Add `KeyboardSensor` to `pipeline/page.tsx` dnd-kit setup; update grip aria-label | U06 |
| Audit `renewals` kanban for same drag-keyboard fix; apply if dnd-kit | U06 |

**Acceptance**: keyboard-only user can navigate all tabs (arrow keys,
home/end), and can move pipeline cards between columns using keyboard
alone. Modal focus trap + Escape covered automatically by `Dialog`
primitive from Tier 2.

### Tier 4 — Polish bundle (~1 day, 1 PR)

The long tail. All small, all using primitives from Tier 2.

| Task                                                       | Severity covered |
|------------------------------------------------------------|------------------|
| Add `frontend/src/app/loading.tsx` with branded skeleton   | U13              |
| Add `frontend/src/app/not-found.tsx` with "Siden ble ikke funnet" | U13       |
| Sweep async fetches: add error state UI using `Alert` primitive | U11         |
| Add loading skeleton to lazy-loaded CRM tab                | U12              |
| SLA wizard "unsaved changes" warning on back/refresh       | U16              |
| Knowledge chat: add `AbortController` + stop button        | U15              |
| Insurers: replace `border-gray-200` with brand token       | U19              |
| IDD: add inline validation hints on required fields        | U18              |
| Per-page `metadata` exports: titles in browser tabs        | U17              |

**Acceptance**: every page in `frontend/src/app/` has a route-specific
`metadata.title`; no async data path lacks an error fallback in the UI.

---

## 5. Verification plan

After each tier:

1. **Manual smoke**: walk the affected surfaces with keyboard only
   (Tab, Shift-Tab, Enter, Escape, arrows). Confirm focus is always
   visible and never trapped.
2. **Automated a11y**: run `axe-core` (via Playwright MCP if available,
   or `@axe-core/cli`) on the top 6 surfaces (dashboard, search, search/[orgnr],
   portfolio, renewals, knowledge). Zero serious or critical violations.
3. **Visual regression**: spot-check staging screenshots match
   pre-change layout (no broken cards, no misaligned tabs, no broken
   responsive collapse).
4. **CI**: existing tests pass; type checking + ruff + frontend lint
   all green per CLAUDE.md commands.

Tier 1 + Tier 2 ship to staging via the normal flow; Tier 1 is
`[skip-staging]`-eligible (low risk, no DB). Tier 2 / 3 / 4 must go
through staging.

---

## 6. Risks and mitigations

| Risk                                                 | Mitigation                                                            |
|------------------------------------------------------|-----------------------------------------------------------------------|
| shadcn install conflicts with existing Tailwind v4 setup | Verify Tailwind version in `package.json` before Tier 2; pin shadcn template accordingly |
| Big diff in Tier 2 (primitive rollout) hard to review| Split Tier 2 into two PRs: (a) primitives + dialogs (b) AppShell hex migration |
| Breaking existing component contracts when swapping in primitives | Each primitive PR includes a snapshot diff of changed component renders; reviewer compares |
| `useRiskConfig()` returning `undefined` during initial load causes layout jump | Set fallback that matches backend defaults; confirm fallback lives in one place (the hook itself) |
| Pipeline keyboard drag conflicts with `@dnd-kit` PointerSensor | `@dnd-kit` supports both sensors simultaneously; verify with manual test in Tier 3 |

---

## 7. Out of scope (explicit)

- Login screen redesign (currently bypassed)
- Backend `RISK_BANDS` schema (already correct)
- Mobile prospecting card layout (separate design effort, U14 deferred)
- Pipeline owner name resolution (needs backend, U20 deferred)
- Visual rebrand or font changes
- Internationalization / English UI (product is Norwegian-only)
- Performance work (bundle size, image optimization)
- Tests-only PRs (test coverage gaps are tracked separately)

---

## 8. Open follow-ups for tracking

After this initiative, file these as separate issues:

- **Hex-code cleanup tracker**: gradual migration of remaining inline
  hex codes outside `ui/` and `AppShell.tsx`. Touch as files are
  otherwise modified.
- **Mobile responsive prospecting table** (U14): needs a card-layout
  design pass.
- **Pipeline user name lookup** (U20): backend endpoint + frontend cache.
- **Login screen UX** when re-enabled.
- **Onboarding tour focus trap** (filed under U10; covered by Dialog
  primitive once OnboardingTour migrates to it — Tier 4 candidate or
  later).
