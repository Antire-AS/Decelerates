# Frontend Usability — Tier 1 (Quick Wins) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship 6 a11y/correctness quick wins across the frontend in a single PR — risk-band hook, htmlFor sweep, skip-to-content, aria-current, focus-visible migration, and an axe-core e2e gate that prevents regressions.

**Architecture:** Pure frontend changes. New SWR hook (`useRiskConfig`) centralises risk-band consumption with a backend-aligned fallback. Mechanical sweeps replace `<label>` without `htmlFor`, replace global `:focus` rings with `:focus-visible`. AppShell gets a skip-to-content link and `aria-current="page"` on the active sidebar item. A new Playwright spec wraps `@axe-core/playwright` to assert WCAG 2.1 AA on the 6 highest-traffic surfaces, gating future regressions.

**Tech Stack:** Next.js 15, React 19, SWR 2.2, Tailwind v3, Playwright 1.59 + `@axe-core/playwright` (new dev dep), TypeScript 5.

**Spec:** [`docs/superpowers/specs/2026-04-17-frontend-usability-audit-design.md`](../specs/2026-04-17-frontend-usability-audit-design.md)

---

## Pre-flight

Before starting:

- [ ] Confirm git state is clean (commit any unrelated work).
- [ ] Confirm backend can be run locally: `bash scripts/run_api.sh` brings up `http://localhost:8000`. `curl http://localhost:8000/risk/config` returns the bands JSON.
- [ ] Confirm frontend dev server runs: `cd frontend && npm run dev` brings up `http://localhost:3000`.
- [ ] Confirm Playwright runs locally: `cd frontend && PLAYWRIGHT_BASE_URL=http://localhost:3000 npx playwright test e2e/smoke.spec.ts -x`. Skip this if Playwright deps aren't installed; the verification spec we add in Task 7 lives in the same e2e dir and will be run by CI.

---

## File structure

**Create:**
- `frontend/src/lib/useRiskConfig.ts` — new hook + fallback constant + band helpers
- `frontend/e2e/a11y.spec.ts` — axe-core smoke test on top 6 surfaces

**Modify:**
- `frontend/src/components/company/RiskBadge.tsx` — use hook
- `frontend/src/components/company/tabs/overview/shared.tsx` — use hook (`riskBandLabel` becomes derived)
- `frontend/src/app/portfolio/page.tsx` — drop `_FALLBACK_BANDS`, use hook
- `frontend/src/app/prospecting/page.tsx` — drop `RISK_BANDS` constant + `riskColor()`, use hook
- `frontend/src/app/portal/[token]/page.tsx` — replace inline thresholds, use hook
- `frontend/src/components/layout/AppShell.tsx` — add `aria-current` and skip link
- `frontend/src/app/layout.tsx` — wrap children in `<main id="main-content">` (skip-link target)
- `frontend/src/app/globals.css` — `:focus` → `:focus-visible` for `.input-sm` and any other interactive ring rules
- ~15 component files using `<label className="label-xs">` — add `htmlFor` + matching input `id`
- `frontend/package.json` — add `@axe-core/playwright` dev dep
- `frontend/package.json` `scripts` — add `test:e2e:a11y` shortcut

---

## Task 1: Create `useRiskConfig` hook with backend-aligned fallback

**Files:**
- Create: `frontend/src/lib/useRiskConfig.ts`

The fallback must match `api/risk.py:29-34` exactly: `[Lav 0-5, Moderat 6-10, Høy 11-15, Svært høy 16-20]`. Today's `_FALLBACK_BANDS` in `portfolio/page.tsx` and `prospecting/page.tsx` use stale ranges (0-3, 4-7, 8-12, 13-20) — that is the bug we are fixing.

- [ ] **Step 1: Write the hook file**

Create `frontend/src/lib/useRiskConfig.ts`:

```typescript
import useSWR from "swr";
import { getRiskConfig, type RiskBand } from "./api";

// Mirrors api/risk.py::RISK_BANDS — keep these two in sync. The hook
// prefers the live /risk/config response; this constant is only used
// before the first response or if the endpoint is unreachable.
export const FALLBACK_RISK_BANDS: readonly RiskBand[] = [
  { label: "Lav",        min: 0,  max: 5,  color: "#27AE60" },
  { label: "Moderat",    min: 6,  max: 10, color: "#C8A951" },
  { label: "Høy",        min: 11, max: 15, color: "#E67E22" },
  { label: "Svært høy",  min: 16, max: 20, color: "#C0392B" },
] as const;

export const UNKNOWN_BAND: RiskBand = {
  label: "Ukjent", min: -1, max: -1, color: "#C4BDB4",
};

const FALLBACK_MAX_SCORE = 20;

export interface UseRiskConfigResult {
  bands: readonly RiskBand[];
  maxScore: number;
  /** Returns the band a score falls into, or UNKNOWN_BAND if score is null/undefined. */
  bandFor: (score?: number | null) => RiskBand;
  /** Index in `bands` for the score, or `bands.length` for unknown. */
  bandIndexFor: (score?: number | null) => number;
}

export function useRiskConfig(): UseRiskConfigResult {
  const { data } = useSWR("risk-config", getRiskConfig, {
    revalidateOnFocus: false,
    revalidateIfStale: false,
    dedupingInterval: 60_000,
  });
  const bands = data?.bands ?? FALLBACK_RISK_BANDS;
  const maxScore = data?.max_score ?? FALLBACK_MAX_SCORE;

  const bandFor = (score?: number | null): RiskBand => {
    if (score == null) return UNKNOWN_BAND;
    for (const b of bands) {
      if (score >= b.min && score <= b.max) return b;
    }
    return bands[bands.length - 1];
  };

  const bandIndexFor = (score?: number | null): number => {
    if (score == null) return bands.length;
    for (let i = 0; i < bands.length; i++) {
      if (score >= bands[i].min && score <= bands[i].max) return i;
    }
    return bands.length - 1;
  };

  return { bands, maxScore, bandFor, bandIndexFor };
}
```

- [ ] **Step 2: Verify the file compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: zero errors. If `RiskBand` import path is wrong, fix it (it should resolve from `@/lib/api` — check `frontend/src/lib/api.ts:882-887`).

- [ ] **Step 3: Lint**

Run: `cd frontend && npx eslint src/lib/useRiskConfig.ts --max-warnings=0`
Expected: zero warnings.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/useRiskConfig.ts
git commit -m "feat(frontend): add useRiskConfig hook with backend-aligned fallback"
```

---

## Task 2: Replace 5 hardcoded risk-band sites with `useRiskConfig`

The hook is the single point of consumption. Each sub-step is one file. After each replacement the file's risk rendering still works because the hook returns the same shape (`RiskBand`) the consumers already expect.

**Files (modify, in order):**
- `frontend/src/components/company/RiskBadge.tsx`
- `frontend/src/components/company/tabs/overview/shared.tsx`
- `frontend/src/app/portfolio/page.tsx`
- `frontend/src/app/prospecting/page.tsx`
- `frontend/src/app/portal/[token]/page.tsx`

- [ ] **Step 1: Replace `RiskBadge.tsx`**

Replace the entire file content with:

```tsx
"use client";

import { useRiskConfig } from "@/lib/useRiskConfig";
import { cn } from "@/lib/cn";

interface RiskBadgeProps {
  score?: number | null;
  className?: string;
}

const EMOJI_BY_LABEL: Record<string, string> = {
  "Lav": "🟢",
  "Moderat": "🟡",
  "Høy": "🔴",
  "Svært høy": "🔴",
  "Ukjent": "⚪",
};

const CSS_BY_LABEL: Record<string, string> = {
  "Lav": "broker-badge-low",
  "Moderat": "broker-badge-mid",
  "Høy": "broker-badge-high",
  "Svært høy": "broker-badge-high",
  "Ukjent": "broker-badge-none",
};

export default function RiskBadge({ score, className }: RiskBadgeProps) {
  const { bandFor } = useRiskConfig();
  const band = bandFor(score);
  const emoji = EMOJI_BY_LABEL[band.label] ?? "";
  const cls = CSS_BY_LABEL[band.label] ?? "broker-badge-none";
  const text = score == null ? "–" : `${emoji} ${band.label}`.trim();
  return <span className={cn(cls, className)}>{text}</span>;
}
```

Note: `RiskBadge` previously had no `"use client"` directive but did not need one (no hooks). Now that it uses `useRiskConfig`, the directive is required.

- [ ] **Step 2: Replace `shared.tsx::riskBandLabel`**

In `frontend/src/components/company/tabs/overview/shared.tsx` lines 12-19, replace:

```tsx
export function riskBandLabel(score?: number): { label: string; guidance: string } {
  if (score == null) return { label: "Ukjent", guidance: "Score ikke beregnet." };
  if (score <= 5) return { label: "Lav", guidance: "Normalpremie forventes. Godt grunnlag for tegning." };
  if (score <= 10) return { label: "Moderat", guidance: "Forvent normal til lett forhøyet premie. Standard tegning." };
  if (score <= 15) return { label: "Høy", guidance: "Forhøyet premie sannsynlig. Krever ekstra dokumentasjon." };
  return { label: "Svært høy", guidance: "Tegning kan være vanskelig. Vurder spesialmarked." };
}
```

with a guidance lookup keyed by band label (the band itself comes from the hook):

```tsx
const GUIDANCE_BY_LABEL: Record<string, string> = {
  "Lav":       "Normalpremie forventes. Godt grunnlag for tegning.",
  "Moderat":   "Forvent normal til lett forhøyet premie. Standard tegning.",
  "Høy":       "Forhøyet premie sannsynlig. Krever ekstra dokumentasjon.",
  "Svært høy": "Tegning kan være vanskelig. Vurder spesialmarked.",
  "Ukjent":    "Score ikke beregnet.",
};

/**
 * Synchronous helper used by callers that already have a band label in hand
 * (e.g., from `useRiskConfig().bandFor(score)`). Returns the broker-facing
 * guidance copy for that band.
 */
export function riskGuidanceForLabel(label: string): string {
  return GUIDANCE_BY_LABEL[label] ?? GUIDANCE_BY_LABEL["Ukjent"];
}
```

Then run a grep to find every caller of the old `riskBandLabel`:

Run: `grep -rn 'riskBandLabel' frontend/src`
Expected output before fix: callers in `frontend/src/components/company/tabs/overview/*`. For each caller, replace:

```tsx
const { label, guidance } = riskBandLabel(score);
```

with:

```tsx
const { bandFor } = useRiskConfig();
const band = bandFor(score);
const guidance = riskGuidanceForLabel(band.label);
const label = band.label;
```

(If a caller is a non-hook context — i.e., not a `"use client"` React component — flag it; it shouldn't exist in this codebase since shared.tsx is rendered client-side.)

- [ ] **Step 3: Replace `portfolio/page.tsx`**

In `frontend/src/app/portfolio/page.tsx`:

1. Delete lines 18-25 (`_FALLBACK_BANDS` and `_UNKNOWN_BAND` constants).
2. Delete the `useSWR("risk-config", ...)` call on line 34 and the `useMemo`-built `RISK_BANDS` and `band` on lines 38-52.
3. Add at the top of the component body:

```tsx
const { bands, bandIndexFor } = useRiskConfig();
const RISK_BANDS = useMemo(() => [...bands, UNKNOWN_BAND], [bands]);
const band = bandIndexFor;
```

4. Update imports: remove `getRiskConfig`, add `useRiskConfig` and `UNKNOWN_BAND`:

```tsx
import { useRiskConfig, UNKNOWN_BAND } from "@/lib/useRiskConfig";
```

5. Remove `getRiskConfig` from the `@/lib/api` import group on lines 5-13.

After the edit, `band` is now a function that returns the index in `bands` (NOT including UNKNOWN_BAND) — but the existing code on line 76 indexes into `RISK_BANDS` (which includes UNKNOWN_BAND at the end). Verify the indexing is still correct: `bandIndexFor(score)` returns `bands.length` for unknown scores, which is exactly the position of `UNKNOWN_BAND` in the new `RISK_BANDS` array. So no further adjustment needed.

- [ ] **Step 4: Replace `prospecting/page.tsx`**

In `frontend/src/app/prospecting/page.tsx`:

1. Delete lines 15-30 (the `RISK_BANDS` constant and `riskColor` function).
2. Inside `ProspectingPage()` add:

```tsx
const { bands, bandFor } = useRiskConfig();
const RISK_BANDS = useMemo(
  () => bands.map(b => ({ ...b, label: `${b.label} (${b.min}–${b.max})` })),
  [bands],
);
const riskColor = (score?: number | null) => bandFor(score).color;
```

3. Add to imports:

```tsx
import { useRiskConfig } from "@/lib/useRiskConfig";
```

4. Find any references to `RISK_BANDS as const` casts and remove them — the new array is no longer `as const` (mapping breaks the literal type). The types still flow correctly through `RiskBand`.

- [ ] **Step 5: Replace `portal/[token]/page.tsx`**

In `frontend/src/app/portal/[token]/page.tsx` lines 87-93, replace:

```tsx
<span className={`text-sm font-bold px-3 py-1 rounded-full ${
  riskScore <= 3 ? "bg-green-100 text-green-700"
  : riskScore <= 7 ? "bg-amber-100 text-amber-700"
  : "bg-red-100 text-red-700"
}`}>
```

with:

```tsx
<span className={`text-sm font-bold px-3 py-1 rounded-full ${
  riskBandClass(bandFor(riskScore).label)
}`}>
```

Add at the top of the file (after `"use client"`):

```tsx
import { useRiskConfig } from "@/lib/useRiskConfig";

const BAND_CLASS: Record<string, string> = {
  "Lav":       "bg-green-100 text-green-700",
  "Moderat":   "bg-amber-100 text-amber-700",
  "Høy":       "bg-red-100 text-red-700",
  "Svært høy": "bg-red-100 text-red-700",
  "Ukjent":    "bg-gray-100 text-gray-700",
};
const riskBandClass = (label: string) => BAND_CLASS[label] ?? BAND_CLASS["Ukjent"];
```

And inside the component body, before the JSX:

```tsx
const { bandFor } = useRiskConfig();
```

- [ ] **Step 6: Verify all hardcoded sites are gone**

Run: `grep -rEn '(RISK_BANDS\\s*=\\s*\\[|_FALLBACK_BANDS|riskColor\\s*\\()' frontend/src`
Expected: zero matches outside `frontend/src/lib/useRiskConfig.ts`.

Run: `grep -rEn 'score\\s*<=\\s*[0-9]+\\s*\\?\\s*"bg-' frontend/src`
Expected: zero matches (no more inline-conditional risk-color classes).

- [ ] **Step 7: Type check + lint**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: zero errors, zero warnings.

- [ ] **Step 8: Manual smoke (local dev)**

Start backend + frontend locally. Visit:
- `http://localhost:3000/portfolio` — risk pie chart should render with 4 bands matching backend (Lav 0-5, Moderat 6-10, Høy 11-15, Svært høy 16-20).
- `http://localhost:3000/search/984851006` (DNB) — risk badge should show "🔴 Høy" if DNB's seeded risk score is in 11-15 range, or "🟡 Moderat" / "🟢 Lav" depending on what's seeded. The label should match what `RiskBadge` derives from `useRiskConfig`.
- `http://localhost:3000/prospecting` — risk filter chips should show "Lav (0–5)", "Moderat (6–10)", etc.

If any badge shows the OLD threshold labels (e.g., "Moderat (4–7)"), the replacement was incomplete — re-grep.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/company/RiskBadge.tsx \
        frontend/src/components/company/tabs/overview/shared.tsx \
        frontend/src/app/portfolio/page.tsx \
        frontend/src/app/prospecting/page.tsx \
        frontend/src/app/portal/[token]/page.tsx
git commit -m "fix(frontend): consume risk bands from /risk/config via useRiskConfig hook

Removes 5 hardcoded threshold sites that diverged from the backend
RISK_BANDS source of truth (api/risk.py). Fallback in useRiskConfig
now matches backend exactly (0-5, 6-10, 11-15, 16-20)."
```

---

## Task 3: Sweep `htmlFor` on `.label-xs` labels

Mechanical fix across ~15 component files. Each `<label className="label-xs">` gets a `htmlFor` and the matching input gets a matching `id`. We use a slug-cased ID derived from the label text or the existing input `name`/`value` attribute.

- [ ] **Step 1: Establish the violation count baseline**

Run: `grep -rEn '<label className="label-xs"' frontend/src/app frontend/src/components | grep -v 'htmlFor' | wc -l`
Expected: a number (currently 64). This number must reach **0** by the end of this task.

- [ ] **Step 2: Generate the fix list**

Run: `grep -rln '<label className="label-xs"' frontend/src/app frontend/src/components`
Expected output: ~15 file paths. Open each and apply the pattern below.

- [ ] **Step 3: Apply the htmlFor pattern (per file)**

For every `<label className="label-xs">…</label>` followed by an `<input>`, `<select>`, or `<textarea>`:

1. Pick a unique `id` for the input. Use a kebab-case slug derived from the label text or, if there's a stateful field, the React state variable name. Within a modal that may render multiple times, prefix with the modal's component name (e.g., `new-deal-title` not just `title`).
2. Add `id="<slug>"` to the input element.
3. Add `htmlFor="<slug>"` to the label element.

Concrete example — `frontend/src/app/sla/page.tsx:276-279`:

Before:
```tsx
<label className="label-xs">Firmanavn *</label>
<input
  className="input-sm"
  value={firmanavn}
  onChange={(e) => setFirmanavn(e.target.value)}
/>
```

After:
```tsx
<label className="label-xs" htmlFor="sla-firmanavn">Firmanavn *</label>
<input
  id="sla-firmanavn"
  className="input-sm"
  value={firmanavn}
  onChange={(e) => setFirmanavn(e.target.value)}
/>
```

- [ ] **Step 4: Verify violation count is zero**

Run: `grep -rEn '<label className="label-xs"' frontend/src/app frontend/src/components | grep -v 'htmlFor' | wc -l`
Expected: `0`.

- [ ] **Step 5: Verify all generic `<label>` (not just `.label-xs`) — second sweep**

Run: `grep -rEn '<label[^>]*>' frontend/src/app frontend/src/components | grep -v 'htmlFor' | grep -v 'sr-only-or-next-element' | head -20`
Expected: an empty list, OR labels that wrap the input directly (`<label><input … /></label>`) — those are valid and need no `htmlFor`.

If any non-wrapping `<label>` without `htmlFor` remains, fix it the same way.

- [ ] **Step 6: Type check + lint**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: zero errors, zero warnings.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/
git commit -m "fix(frontend): add htmlFor to all .label-xs labels for screen readers

Sweeps ~15 form files to associate every <label> with its <input>,
<select>, or <textarea> via htmlFor + matching id. Resolves WCAG
1.3.1 (Info and Relationships) and 4.1.2 (Name, Role, Value) gaps."
```

---

## Task 4: Add skip-to-content link in AppShell

The skip link is the first focusable element on the page. Pressing Tab on page load focuses it; pressing Enter jumps focus to `#main-content`, bypassing the 12+ sidebar nav items.

**Files:**
- Modify: `frontend/src/app/layout.tsx`
- Modify: `frontend/src/components/layout/AppShell.tsx`
- Modify: `frontend/src/app/globals.css`

- [ ] **Step 1: Add the `id` to the main content wrapper**

In `frontend/src/components/layout/AppShell.tsx` line 215, change:

```tsx
<main className="flex-1 overflow-y-auto bg-[#F5F0EB]">
```

to:

```tsx
<main id="main-content" tabIndex={-1} className="flex-1 overflow-y-auto bg-[#F5F0EB]">
```

`tabIndex={-1}` makes `<main>` programmatically focusable (so the browser actually moves focus there when the skip link is activated) without putting it in the natural Tab order.

- [ ] **Step 2: Add the skip link as the first child of AppShell**

In `frontend/src/components/layout/AppShell.tsx`, after line 156 (`return (`) and inside the outer `<div>`, add as the first child:

```tsx
<a
  href="#main-content"
  className="skip-to-content"
>
  Hopp til hovedinnhold
</a>
```

The full opening of the JSX becomes:

```tsx
return (
  <div className="flex h-screen overflow-hidden">
    <a href="#main-content" className="skip-to-content">
      Hopp til hovedinnhold
    </a>
    {/* ── Desktop sidebar (md+) ─────────────────────────────────────── */}
    <aside className="hidden md:flex w-56 flex-shrink-0 bg-[#F5F0EB] border-r border-[#D4C9B8] flex-col">
```

- [ ] **Step 3: Add the skip-link CSS**

In `frontend/src/app/globals.css`, inside `@layer components`, add:

```css
.skip-to-content {
  @apply sr-only;
}
.skip-to-content:focus {
  @apply not-sr-only fixed top-2 left-2 z-[100] bg-[#2C3E50] text-white
         px-4 py-2 rounded-lg text-sm font-medium shadow-lg outline-none
         ring-2 ring-[#C5D8F0];
}
```

(`sr-only` and `not-sr-only` are built into Tailwind. `z-[100]` puts it above the mobile drawer's `z-50`.)

- [ ] **Step 4: Manual keyboard verification**

Start dev. Visit `http://localhost:3000/dashboard`. Press Tab once. Expected: a "Hopp til hovedinnhold" pill appears at the top-left corner. Press Enter. Expected: focus moves into the `<main>` content area; pressing Tab again focuses the first interactive element inside `<main>` (e.g., a card link), NOT a sidebar nav item.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/layout.tsx frontend/src/components/layout/AppShell.tsx frontend/src/app/globals.css
git commit -m "feat(frontend): add skip-to-content link in AppShell (WCAG 2.4.1)"
```

(`layout.tsx` may not need to change. If it doesn't, drop it from the `git add` line.)

---

## Task 5: Add `aria-current="page"` on active sidebar nav

**Files:**
- Modify: `frontend/src/components/layout/AppShell.tsx`

- [ ] **Step 1: Modify the active-detection in the nav loop**

In `frontend/src/components/layout/AppShell.tsx` lines 80-93, update the `<Link>` element. Change:

```tsx
{NAV_ITEMS.map(({ href, label, icon: Icon }) => (
  <Link
    key={href}
    href={href}
    onClick={onNavClick}
    className={cn(
      "nav-item",
      pathname.startsWith(href) && "nav-item-active",
    )}
  >
```

to:

```tsx
{NAV_ITEMS.map(({ href, label, icon: Icon }) => {
  const isActive = pathname.startsWith(href);
  return (
    <Link
      key={href}
      href={href}
      onClick={onNavClick}
      aria-current={isActive ? "page" : undefined}
      className={cn(
        "nav-item",
        isActive && "nav-item-active",
      )}
    >
```

And update the closing tag to match the new map body (add a `}` and `)` for the arrow function and ternary).

- [ ] **Step 2: Verify**

Run: `grep -n 'aria-current' frontend/src/components/layout/AppShell.tsx`
Expected: one match on the Link element.

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: zero errors, zero warnings.

- [ ] **Step 3: Manual verification**

Start dev. Visit `/dashboard`. Open devtools accessibility panel. Inspect the "Hjem" sidebar item. Expected: ARIA attributes show `aria-current: page`. Visit `/portfolio`. The "Hjem" item no longer has `aria-current`; "Portefølje" has it.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/layout/AppShell.tsx
git commit -m "feat(frontend): aria-current=\"page\" on active sidebar nav (WCAG 4.1.2)"
```

---

## Task 6: Migrate `:focus` rings → `:focus-visible`

`:focus-visible` shows the focus ring only when the user navigates by keyboard (Tab) — it stays hidden on mouse clicks. This eliminates the visual clutter of focus rings appearing after every button click while preserving the keyboard a11y signal.

**Files:**
- Modify: `frontend/src/app/globals.css`
- Modify: any component file with inline `focus:ring-` (without `-visible`) classes

- [ ] **Step 1: Update `globals.css` `.input-sm`**

In `frontend/src/app/globals.css` line 51-54, change:

```css
.input-sm {
  @apply w-full px-2 py-1.5 text-xs border border-[#D4C9B8] rounded-lg bg-white
         focus:outline-none focus:ring-1 focus:ring-[#4A6FA5];
}
```

to:

```css
.input-sm {
  @apply w-full px-2 py-1.5 text-xs border border-[#D4C9B8] rounded-lg bg-white
         focus:outline-none focus-visible:ring-1 focus-visible:ring-[#4A6FA5];
}
```

- [ ] **Step 2: Find component-level `focus:ring-` violations**

Run: `grep -rEn 'focus:ring-' frontend/src | grep -v 'focus-visible:ring-'`
Expected: a list of N matches. Capture the count; the goal is **zero**.

- [ ] **Step 3: Replace each match**

For each matched file, change `focus:ring-` to `focus-visible:ring-`. Also change the paired `focus:outline-none` to remain `focus:outline-none` (still want NO outline regardless of focus type — that part stays). Where you see `focus:border-` paired with `focus:ring-`, leave the border change as `focus:` (border on click is harmless and matches existing input-style affordance).

A safe codemod with `sed` (run from repo root, only on tracked frontend files):

```bash
git ls-files frontend/src | xargs sed -i '' 's/focus:ring-/focus-visible:ring-/g'
```

(macOS BSD `sed` syntax — uses `-i ''`. On Linux drop the `''`.)

- [ ] **Step 4: Verify**

Run: `grep -rEn 'focus:ring-' frontend/src | grep -v 'focus-visible:ring-'`
Expected: zero matches.

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: zero errors, zero warnings.

- [ ] **Step 5: Manual verification**

Start dev. Visit `/dashboard`. Click anywhere on a button or input — focus ring should NOT appear (or should appear and disappear without lingering). Press Tab — focus ring SHOULD appear on each focused element. Test on `/sla` (form-heavy), `/search` (input-heavy), `/portfolio` (button-heavy).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/
git commit -m "fix(frontend): use :focus-visible for keyboard-only focus rings

Mouse clicks no longer leave focus rings on buttons/inputs while
keyboard navigation still shows them. Reduces visual clutter without
sacrificing a11y."
```

---

## Task 7: Add axe-core e2e gate

Locks in the Tier 1 wins so future PRs can't regress them. The spec runs against 6 surfaces: `/dashboard`, `/search`, `/search/984851006` (DNB profile), `/portfolio`, `/renewals`, `/knowledge`.

**Files:**
- Create: `frontend/e2e/a11y.spec.ts`
- Modify: `frontend/package.json` (add `@axe-core/playwright`, add npm script)

- [ ] **Step 1: Add the dev dependency**

Run: `cd frontend && npm install --save-dev @axe-core/playwright`
Expected: `package.json` and `package-lock.json` updated; one new entry under `devDependencies`.

- [ ] **Step 2: Add the npm script**

In `frontend/package.json` `scripts`, add:

```json
"test:e2e:a11y": "playwright test e2e/a11y.spec.ts"
```

after the existing `test:e2e:llm` line.

- [ ] **Step 3: Write the spec**

Create `frontend/e2e/a11y.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/**
 * WCAG 2.1 AA gate — runs axe-core against the 6 highest-traffic
 * broker surfaces. Any new "serious" or "critical" violation fails the
 * test. Tier 1 of the 2026-04-17 usability initiative locked in the
 * baseline; this spec prevents regressions.
 *
 * Excluded rules (rationale per rule):
 *   - color-contrast: brand palette has been manually verified above
 *     AAA on text. Re-enable when Tier 2 introduces shadcn primitives
 *     and we can audit each component once.
 *
 * The seeded DNB orgnr (984851006) is always available in staging and
 * matches the search-flow.spec.ts fixture.
 */

const DNB_ORGNR = "984851006";

const SURFACES: Array<{ path: string; label: string }> = [
  { path: "/dashboard", label: "dashboard" },
  { path: "/search", label: "search" },
  { path: `/search/${DNB_ORGNR}`, label: "search/[orgnr]" },
  { path: "/portfolio", label: "portfolio" },
  { path: "/renewals", label: "renewals" },
  { path: "/knowledge", label: "knowledge" },
];

for (const { path, label } of SURFACES) {
  test(`a11y: ${label} has no serious or critical axe violations`, async ({ page }) => {
    await page.goto(path);
    // Give SWR fetches and lazy-loaded tab content a moment to render.
    await page.waitForLoadState("networkidle", { timeout: 30_000 });
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .disableRules(["color-contrast"])
      .analyze();

    const blocking = results.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical",
    );

    if (blocking.length > 0) {
      // Pretty-print the violations so CI logs are actionable.
      console.error(
        `Axe violations on ${label}:\n` +
          blocking
            .map(
              (v) =>
                `  [${v.impact}] ${v.id}: ${v.help}\n` +
                v.nodes.map((n) => `    - ${n.target.join(", ")}`).join("\n"),
            )
            .join("\n"),
      );
    }
    expect(blocking, `Axe found ${blocking.length} serious/critical violations on ${label}`).toEqual([]);
  });
}
```

- [ ] **Step 4: Run the spec locally against localhost**

Start backend + frontend locally. Then:

Run: `cd frontend && PLAYWRIGHT_BASE_URL=http://localhost:3000 npx playwright test e2e/a11y.spec.ts`
Expected: all 6 tests PASS.

If any fail with violations introduced by Tier 1 work (label, aria-current, focus-visible, skip-link), inspect the failure, fix the root cause, and re-run.

If a failure is a pre-existing violation NOT covered by Tier 1 (e.g., something in `/renewals` related to drag-and-drop a11y), that's expected — Tier 3 will fix it. For now, add the offending rule ID to `.disableRules([])` with an inline comment naming the tier that owns the fix:

```typescript
.disableRules([
  "color-contrast",
  "aria-allowed-role", // owned by Tier 3 (ARIA tabs migration)
])
```

This keeps the gate green for Tier 1 without papering over real issues — every disabled rule has a named owner-tier.

- [ ] **Step 5: Commit**

```bash
git add frontend/e2e/a11y.spec.ts frontend/package.json frontend/package-lock.json
git commit -m "test(frontend): add axe-core e2e gate for top 6 surfaces

Runs WCAG 2.1 AA scan via @axe-core/playwright on dashboard, search,
search/[orgnr], portfolio, renewals, knowledge. Fails on any serious
or critical violation. Locks in Tier 1 wins."
```

---

## Task 8: Final verification + push

- [ ] **Step 1: Type check + lint**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: zero errors, zero warnings.

- [ ] **Step 2: Full e2e smoke + a11y**

Start backend + frontend locally. Then:

Run: `cd frontend && PLAYWRIGHT_BASE_URL=http://localhost:3000 npx playwright test e2e/smoke.spec.ts e2e/search-flow.spec.ts e2e/portfolio-flow.spec.ts e2e/a11y.spec.ts`
Expected: all tests PASS.

- [ ] **Step 3: Manual keyboard pass**

Open `/dashboard` in a browser. Using ONLY the keyboard:
1. Press Tab — skip link appears.
2. Enter — focus jumps to `<main>`.
3. Tab through dashboard cards — focus visible on each. Mouse-click a card link, then Tab again from a different page (or refresh) — confirm clicks alone don't leave a focus ring on the clicked element.
4. Open `/sla` — Tab through the wizard form — every input should be reachable; pressing Tab on a label-then-input pair lands on the input (proves htmlFor association doesn't break tab order).
5. Visit each sidebar route via mouse — confirm the active item shows `aria-current="page"` (devtools → Accessibility panel).

Document any issues in the PR description.

- [ ] **Step 4: Push to staging via PR**

```bash
git push -u origin <branch-name>
gh pr create --base staging --title "frontend: Tier 1 usability quick wins (a11y + risk-band hook)" --body "$(cat <<'EOF'
## Summary
Implements Tier 1 of the 2026-04-17 frontend usability initiative.

- New `useRiskConfig` hook centralises risk-band consumption with a backend-aligned fallback (0-5/6-10/11-15/16-20). Removes 5 hardcoded threshold sites that diverged from `api/risk.py::RISK_BANDS`.
- `htmlFor` swept across ~15 form files; every `<label>` now associated with its input. Resolves WCAG 1.3.1 / 4.1.2 gaps.
- AppShell skip-to-content link (WCAG 2.4.1) + `aria-current="page"` on active nav (WCAG 4.1.2).
- Global `:focus` → `:focus-visible` so mouse clicks no longer leave lingering focus rings.
- New `e2e/a11y.spec.ts` runs `@axe-core/playwright` against 6 top surfaces; fails on any serious/critical violation. Locks in the Tier 1 baseline.

Spec: `docs/superpowers/specs/2026-04-17-frontend-usability-audit-design.md`
Plan: `docs/superpowers/plans/2026-04-17-frontend-usability-tier1.md`

## Test plan
- [ ] CI green (lint, type check, e2e smoke + a11y)
- [ ] Manual keyboard walk on staging: skip link visible on Tab, jumps to main on Enter
- [ ] DNB profile risk badge shows correct label per backend bands
- [ ] Portfolio risk pie chart shows 4 bands matching backend
- [ ] Active sidebar item announces `aria-current="page"` in devtools

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 5: After staging deploy, run a11y against staging**

Once the staging deploy completes:

Run: `cd frontend && npx playwright test e2e/a11y.spec.ts`
(Default `PLAYWRIGHT_BASE_URL` in `playwright.config.ts` points at staging.)

Expected: all 6 tests PASS against staging.

If green, the PR is ready to promote to main per the standard `staging → main` flow.

---

## Done criteria

- All checkboxes above ticked.
- `grep -rE "(RISK_BANDS\\s*=\\s*\\[|_FALLBACK_BANDS|riskColor\\s*\\()" frontend/src` returns only matches inside `frontend/src/lib/useRiskConfig.ts`.
- `grep -rE '<label[^>]*>' frontend/src | grep -v 'htmlFor'` returns only label elements that wrap their input directly (no flat label-then-input pairs without `htmlFor`).
- `grep -rE 'focus:ring-' frontend/src | grep -v 'focus-visible:ring-'` returns zero matches.
- `npm run test:e2e:a11y` passes on staging.
- PR open against staging branch with the description in Task 8 Step 4.

## Out of scope (explicit)

- Replacing `confirm()` / `alert()` calls — Tier 2 owns this (needs Dialog primitive).
- Migrating inline hex codes to semantic Tailwind classes — Tier 2.
- ARIA tabs pattern for `/search/[orgnr]` and `/portfolio/analytics` — Tier 3.
- Pipeline keyboard drag — Tier 3.
- Per-page metadata, loading.tsx, not-found.tsx — Tier 4.
