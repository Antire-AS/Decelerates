# Product UX Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship four independent product features that build on the Tier 1-4 usability foundation — dark mode, `⌘K` command palette, user-facing accessibility preferences, and activation of the existing-but-unused i18n infrastructure.

**Architecture:** Four separate phases, each landing as its own PR against `staging` then promoting to `main`. The phases are independent (no dependencies between them) so they can ship in any order, but the recommended sequence is Dark mode → Command palette → A11y preferences → i18n activation. Every phase builds on the CSS-variable-driven theming system that Tier 2 established in `frontend/src/app/globals.css` + `frontend/tailwind.config.ts`.

**Tech Stack:** Next.js 15 (app router), React 19, TypeScript 5, Tailwind v3.4, `next-themes` (new — dark mode), `cmdk` (new — command palette), existing `LanguageProvider` context at `frontend/src/lib/i18n.tsx` (existing — activation only, no new lib).

**Spec:** this document (plan + spec combined — the phase-introductions act as mini-specs).
**Predecessor:** `docs/superpowers/plans/2026-04-17-frontend-usability-tier4.md` (landed as PR #111, staging commit `55fe4a6`, prod commit `6e8cfd6`).

---

## Background and state of play

### What's already in place after Tier 4

- **shadcn primitives** live in `frontend/src/components/ui/` (13 files): `alert, badge, button, card, confirm-dialog, dialog, dropdown-menu, input, select, skeleton, tabs, textarea, tooltip`.
- **Brand tokens + shadcn HSL variables** are wired in `frontend/tailwind.config.ts` and `frontend/src/app/globals.css`. Every component that uses `bg-background`, `text-foreground`, `border-brand-stone`, etc. is theme-ready.
- **Root layout** (`frontend/src/app/layout.tsx`) wraps everything in `<html lang="no">` → `<Providers>` → `<LanguageProvider>` → `<AppShell>`.
- **i18n scaffolding** at `frontend/src/lib/i18n.tsx`: `LanguageProvider` context + `useT()` hook + `translations.json` (100+ Norwegian/English key pairs, 537 lines). **But `useT()` is called by exactly 1 file in the codebase** (`frontend/src/app/api/portfolio/[id]/ingest-stream/route.ts`) — so the whole UI sweep is still ahead of us.

### Scope decisions per phase

| Phase | Scope today | Deferred |
|-------|-------------|----------|
| Dark mode | Theme toggle + dark palette + `prefers-color-scheme` default + `next-themes` wiring + audit of shadcn-ish components | Full sweep of ~600 remaining inline hex codes (tracked in #105) |
| Command palette | `⌘K`/`Ctrl+K` opens palette; route navigation (20 routes) + live company-search by orgnr/name via existing `/search` endpoint | Document search, workflow actions ("Create IDD", "Generate SLA"), recent-actions history |
| A11y preferences | User menu entry → panel with: font-size slider (3 levels), `prefers-reduced-motion` respect + toggle, high-contrast toggle | Voice input, keyboard-shortcut cheat-sheet overlay, reading-guide ruler |
| i18n activation | Locale switcher in user menu; localStorage persistence; `<html lang>` sync; sweep of AppShell nav + dashboard titles + top-level page headings (~50 strings covered by existing `translations.json`) | Full sweep of every UI string across 20 routes (tracked as follow-up issue to be filed at end of this phase) |

Each phase should ship in 1-2 days of focused work. If any phase balloons past 3 days, stop and file a follow-up issue rather than silently expanding scope.

---

## Pre-flight (one-time for the whole plan)

- [ ] Confirm you're on a clean `main` synced with `origin/main` (`6e8cfd6` or later).
- [ ] Confirm `.worktrees/` is gitignored (`grep -n worktrees .gitignore` returns a match).
- [ ] Confirm local dev stack runs: `docker compose up postgres -d` + `bash scripts/run_api.sh` (http://localhost:8000/ping returns `{"ok":true}`) + `cd frontend && npm run dev` (http://localhost:3000/dashboard loads).

---

# Phase 1 — Dark mode

**Goal:** Every page renders correctly in both light and dark themes; the user toggles via a sun/moon button in AppShell header; the initial theme respects `prefers-color-scheme`; the choice persists across sessions.

**Approach:** Adopt `next-themes` (the de-facto standard for Next.js + shadcn), which sets a `class="dark"` on `<html>`. Our existing shadcn HSL variables (`--background`, `--foreground`, `--primary`, etc.) in `globals.css` already flip correctly when that class is present — we just need to define the `.dark` variant. The brand palette (`--brand-dark`, `--brand-mid`, etc.) gets parallel dark-mode equivalents.

**File structure for Phase 1:**

- Create: `frontend/src/components/theme-provider.tsx` — thin wrapper around `next-themes` `ThemeProvider`.
- Create: `frontend/src/components/theme-toggle.tsx` — sun/moon dropdown that calls `useTheme().setTheme`.
- Modify: `frontend/src/app/layout.tsx` — inject `<ThemeProvider>` under `<Providers>`; add `suppressHydrationWarning` on `<html>`.
- Modify: `frontend/src/app/globals.css` — add `.dark` block defining dark variants of all shadcn HSL variables and brand colors.
- Modify: `frontend/src/components/layout/AppShell.tsx` — render `<ThemeToggle />` in the top-right header area (near the user menu).
- Modify: `frontend/package.json` — `+ "next-themes": "^0.4.4"` (or latest).

### Task 1.1: Install `next-themes`

**Files:**
- Modify: `frontend/package.json`, `frontend/package-lock.json`

- [ ] **Step 1: Install the dep**

```bash
cd /Users/tharusan/Projects/Decelerates/.worktrees/dark-mode/frontend
npm install next-themes
```

Expected: one new entry in `dependencies`, lockfile updated.

- [ ] **Step 2: Commit**

```bash
cd /Users/tharusan/Projects/Decelerates/.worktrees/dark-mode
git add frontend/package.json frontend/package-lock.json
git commit -m "chore(frontend): add next-themes dep for dark mode"
```

### Task 1.2: Add dark palette to `globals.css`

**Files:**
- Modify: `frontend/src/app/globals.css`

Tier 2 left `:root` with the light-mode HSL variables. We add a sibling `.dark` block that redefines each variable for dark mode. The brand tokens (`--brand-dark`, etc.) stay identical — dark mode only flips the shadcn semantic tokens that drive surface color.

- [ ] **Step 1: Read the current `:root` block**

```bash
grep -n "^:root\|^\.dark\|--background\|--brand-" frontend/src/app/globals.css | head -40
```

Expected: the `:root { --brand-dark: ...; --background: ...; ... }` block from Tier 2 exists. No `.dark` block yet.

- [ ] **Step 2: Insert the `.dark` block immediately after `:root`**

After the closing `}` of `:root`, insert:

```css
.dark {
  /* Surfaces */
  --background:      210 29% 13%;  /* near-black with brand-dark hue */
  --foreground:      38 25% 94%;   /* brand-beige as light-on-dark text */

  --card:            210 29% 16%;  /* one step lighter than bg */
  --card-foreground: 38 25% 94%;

  --popover:            210 29% 16%;
  --popover-foreground: 38 25% 94%;

  /* Interactives */
  --primary:           215 57% 70%;  /* brand-light as the primary in dark mode */
  --primary-foreground: 210 29% 13%;

  --secondary:           36 18% 30%;  /* dark brand-stone */
  --secondary-foreground: 38 25% 94%;

  --muted:             28 11% 40%;    /* dark brand-muted */
  --muted-foreground:  38 18% 78%;    /* brand-stone-ish */

  --accent:             215 34% 47%;  /* brand-mid in dark */
  --accent-foreground:  38 25% 94%;

  --destructive:           5 64% 59%;   /* slightly brighter danger */
  --destructive-foreground: 38 25% 94%;

  /* Borders + inputs */
  --border:  210 20% 25%;
  --input:   210 20% 25%;
  --ring:    215 57% 70%;
}
```

- [ ] **Step 3: Add a matching scrollbar / body-bg override (optional polish)**

Also in `globals.css`, at the bottom of the `@layer base` block:

```css
html, body {
  background-color: hsl(var(--background));
  color: hsl(var(--foreground));
}
```

This guarantees that routes without `<AppShell>` (e.g., `/portal/[token]`) still respect the theme.

- [ ] **Step 4: Typecheck**

```bash
cd frontend
npx tsc --noEmit
```
Expected: clean.

- [ ] **Step 5: Commit**

```bash
cd /Users/tharusan/Projects/Decelerates/.worktrees/dark-mode
git add frontend/src/app/globals.css
git commit -m "feat(frontend): add dark-mode HSL tokens in globals.css"
```

### Task 1.3: Create `ThemeProvider` wrapper

**Files:**
- Create: `frontend/src/components/theme-provider.tsx`

- [ ] **Step 1: Write the file**

```tsx
"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { ComponentProps } from "react";

type ThemeProviderProps = ComponentProps<typeof NextThemesProvider>;

export function ThemeProvider({ children, ...props }: ThemeProviderProps) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
      {...props}
    >
      {children}
    </NextThemesProvider>
  );
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend && npx tsc --noEmit
```
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/theme-provider.tsx
git commit -m "feat(frontend): add ThemeProvider wrapper around next-themes"
```

### Task 1.4: Wire `ThemeProvider` into root layout

**Files:**
- Modify: `frontend/src/app/layout.tsx`

- [ ] **Step 1: Read current layout**

```bash
cat frontend/src/app/layout.tsx
```
Expected: the content from Tier 4 — imports `Providers`, `LanguageProvider`, `AppShell`, `ErrorBoundary`, `Toaster`; wraps `<html lang="no">` → `<body>` → `<Providers>` → `<LanguageProvider>` → `<AppShell>`.

- [ ] **Step 2: Add `suppressHydrationWarning` + `ThemeProvider`**

Replace the component body with:

```tsx
import type { Metadata } from "next";
import "./globals.css";
import { LanguageProvider } from "@/lib/i18n";
import AppShell from "@/components/layout/AppShell";
import Providers from "@/providers";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { ThemeProvider } from "@/components/theme-provider";
import { Toaster } from "sonner";

export const metadata: Metadata = {
  title: "Broker Accelerator",
  description: "Forsikringsmegling · Due Diligence · Risikoprofil",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="no" suppressHydrationWarning>
      <body>
        <ThemeProvider>
          <Providers>
            <LanguageProvider>
              <AppShell>
                <ErrorBoundary>{children}</ErrorBoundary>
              </AppShell>
            </LanguageProvider>
            <Toaster richColors closeButton position="top-right" />
          </Providers>
        </ThemeProvider>
      </body>
    </html>
  );
}
```

`suppressHydrationWarning` on `<html>` is required because `next-themes` writes the `class="dark"` attribute before React hydrates; without it React would log a hydration mismatch warning.

- [ ] **Step 3: Typecheck + lint**

```bash
cd frontend
npx tsc --noEmit && npm run lint
```
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/layout.tsx
git commit -m "feat(frontend): wire ThemeProvider under root layout"
```

### Task 1.5: Build the `ThemeToggle` component

**Files:**
- Create: `frontend/src/components/theme-toggle.tsx`

- [ ] **Step 1: Write the file**

```tsx
"use client";

import * as React from "react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export function ThemeToggle() {
  const { setTheme } = useTheme();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Bytt tema">
          <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
          <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
          <span className="sr-only">Bytt tema</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => setTheme("light")}>Lyst</DropdownMenuItem>
        <DropdownMenuItem onClick={() => setTheme("dark")}>Mørkt</DropdownMenuItem>
        <DropdownMenuItem onClick={() => setTheme("system")}>System</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend && npx tsc --noEmit
```
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/theme-toggle.tsx
git commit -m "feat(frontend): add ThemeToggle dropdown (sun/moon/system)"
```

### Task 1.6: Render `ThemeToggle` in AppShell header

**Files:**
- Modify: `frontend/src/components/layout/AppShell.tsx`

- [ ] **Step 1: Find the top-right header area**

```bash
grep -n 'flex.*items-center.*gap' frontend/src/components/layout/AppShell.tsx | head -5
```

Locate the header bar. It typically contains the user menu, notifications, or other top-right elements. If none exists, add a small header row at the top of the main content area.

- [ ] **Step 2: Import `ThemeToggle`**

Add to the imports of `AppShell.tsx`:

```tsx
import { ThemeToggle } from "@/components/theme-toggle";
```

- [ ] **Step 3: Insert `<ThemeToggle />` into the header**

Place the `<ThemeToggle />` in the header area. If the header is a `<div className="flex items-center gap-2">`, append `<ThemeToggle />` at the end so it sits at the rightmost position.

Concrete example: if AppShell currently has something like:

```tsx
<header className="flex items-center justify-between border-b px-4 py-2">
  <h1>Broker Accelerator</h1>
  <div className="flex items-center gap-2">
    <UserMenu />
  </div>
</header>
```

Change it to:

```tsx
<header className="flex items-center justify-between border-b px-4 py-2">
  <h1>Broker Accelerator</h1>
  <div className="flex items-center gap-2">
    <ThemeToggle />
    <UserMenu />
  </div>
</header>
```

If there's no header bar at all (AppShell jumps straight into sidebar + main), add a minimal header row above `{children}`:

```tsx
<div className="flex items-center justify-end border-b border-brand-stone px-4 py-2">
  <ThemeToggle />
</div>
```

- [ ] **Step 4: Typecheck + lint**

```bash
cd frontend
npx tsc --noEmit && npm run lint
```
Expected: clean.

- [ ] **Step 5: Manual smoke**

```bash
npm run dev
```

Visit http://localhost:3000/dashboard. Click the sun icon (top-right). Choose "Mørkt" — the page should flip to dark. Choose "System" — it should follow OS setting. Refresh the page: the chosen theme persists.

Spot-check other routes: `/search`, `/portfolio`, `/renewals`, `/knowledge`, `/sla`, `/idd`, `/pipeline`. Look for unreadable text or invisible borders.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/layout/AppShell.tsx
git commit -m "feat(frontend): add ThemeToggle to AppShell header"
```

### Task 1.7: Audit and fix dark-mode regressions

Almost certainly some components have hardcoded hex colors (`[#2C3E50]`, `[#F5F0EB]`, etc.) that look wrong in dark mode. A full sweep is tracked in #105; this task only fixes the dark-mode-BROKEN ones.

- [ ] **Step 1: Enumerate hardcoded colors**

```bash
grep -rE '\[#[0-9A-Fa-f]{6}\]' frontend/src --include="*.tsx" | wc -l
```

Expected: a large number (hundreds). We are NOT fixing all of them — only the ones that break dark mode.

- [ ] **Step 2: Visual audit (manual)**

With `npm run dev` running in dark mode, visit each of the 6 top surfaces:

- `/dashboard`
- `/search`
- `/search/984851006`
- `/portfolio`
- `/renewals`
- `/knowledge`

For each, note any element that is unreadable or visually broken (e.g., `text-[#2C3E50]` text on a dark background). Take screenshots.

- [ ] **Step 3: Fix the broken elements**

For each broken element, replace the inline hex with the corresponding semantic token:

| Inline hex (light-mode intent) | Dark-mode-safe replacement |
|--------------------------------|----------------------------|
| `text-[#2C3E50]` (main text) | `text-foreground` |
| `text-[#8A7F74]` (muted text) | `text-muted-foreground` |
| `bg-[#F5F0EB]` (page bg) | `bg-background` |
| `bg-[#EDE8E3]` (hover tint) | `bg-muted` |
| `border-[#D4C9B8]` (input border) | `border-input` or `border-border` |
| `border-[#EDE8E3]` (card border) | `border-border` |

Only fix the elements that ACTUALLY break in dark mode. The rest are tracked in #105 and should be left alone.

- [ ] **Step 4: Re-smoke in dark mode**

Rerun the visual audit. Confirm no remaining unreadable / broken elements on the 6 top surfaces.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "fix(frontend): replace dark-mode-broken inline hex codes with semantic tokens

Visual audit found N hardcoded colors that rendered unreadably in dark
mode on the 6 top surfaces. Replaced with the matching shadcn
semantic tokens (text-foreground, bg-background, border-border, etc.).
The broader hex cleanup is tracked in #105 and is out of scope here."
```

Replace `N` with the actual count after the fix.

### Task 1.8: Final verification + PR

- [ ] **Step 1: Full lint + typecheck + build**

```bash
cd /Users/tharusan/Projects/Decelerates/.worktrees/dark-mode/frontend
npx tsc --noEmit && npm run lint && npm run build
```
All three must pass.

- [ ] **Step 2: api-types-fresh check**

```bash
npm run gen:api-types
git diff --exit-code src/lib/api-schema.ts
```
Expected: no diff.

- [ ] **Step 3: jscpd check**

```bash
cd /Users/tharusan/Projects/Decelerates/.worktrees/dark-mode
npx jscpd --ignore '**/__pycache__/**,**/.venv/**,**/node_modules/**,**/.git/**,uv.lock,**/.next/**,**/video/node_modules/**' --silent 2>&1 | tail -3
```
Expected: duplication % below the 5% threshold.

- [ ] **Step 4: Push + open PR**

```bash
git push -u origin feat/dark-mode

gh pr create --base staging --title "feat(frontend): dark mode (next-themes + ThemeToggle)" --body "$(cat <<'EOF'
## Summary

Phase 1 of the 2026-04-18 product UX expansion (plan: \`docs/superpowers/plans/2026-04-18-product-ux-expansion.md\`).

- Adds \`next-themes\` dep and a thin \`ThemeProvider\` wrapper under the root layout.
- Adds a \`ThemeToggle\` (sun / moon / system) dropdown in the AppShell header.
- Adds the \`.dark\` HSL variable block in \`globals.css\` — surfaces, interactives, and borders all flip cleanly via the existing Tier 2 shadcn token system.
- Visual audit + targeted fix of dark-mode-broken inline hex codes on the 6 top surfaces (dashboard, search, search/[orgnr], portfolio, renewals, knowledge). Broader hex cleanup remains in #105.

## Test plan

- [ ] Toggle light / dark / system on each of the 6 top surfaces.
- [ ] Verify system mode follows OS preference.
- [ ] Verify theme persists across refresh (\`localStorage.theme\`).
- [ ] Verify no hydration warnings in the console.

## Out of scope

- Full hex-code cleanup (#105).
- Custom colors for charts (Recharts uses its own palette — left alone).
EOF
)"
```

- [ ] **Step 5: Wait for CI, merge**

```bash
# Monitor
until gh pr view <PR_NUM> --json statusCheckRollup --jq '[.statusCheckRollup[]? | select(.status == "IN_PROGRESS" or .status == "QUEUED")] | length' | grep -qx "0"; do sleep 15; done
# Verify green
gh pr view <PR_NUM> --json mergeable,mergeStateStatus
# Merge
bash scripts/merge-pr.sh <PR_NUM> staging
```

### Done criteria — Phase 1

- Dark mode toggle exists and works on all 6 top surfaces.
- No unreadable text or invisible borders in dark mode.
- `localStorage.theme` persists the choice.
- CI green; PR merged to staging.

---

# Phase 2 — Command palette (⌘K)

**Goal:** Press `⌘K` (macOS) or `Ctrl+K` (Win/Linux) anywhere in the app to open a search-and-jump palette. Two item types: **route shortcuts** (20 top-level routes) and **company search** (orgnr / name, hits the existing `/companies` endpoint with live debounced query).

**Approach:** Install the `cmdk` primitive (used by shadcn's `Command` component). Add a new `frontend/src/components/command-palette.tsx` that wraps `cmdk.Dialog` and wires keybinds, route list, and debounced company search. Mount it once in `AppShell` so it's globally available.

**File structure for Phase 2:**

- Create: `frontend/src/components/ui/command.tsx` — shadcn canonical `Command` primitive (`Command`, `CommandDialog`, `CommandInput`, `CommandList`, `CommandGroup`, `CommandItem`, `CommandEmpty`).
- Create: `frontend/src/components/command-palette.tsx` — the actual palette component with the routes + search logic.
- Modify: `frontend/src/components/layout/AppShell.tsx` — mount `<CommandPalette />` once near the top of the tree.
- Modify: `frontend/package.json` — `+ "cmdk": "^1.0.0"` (or latest).

### Task 2.1: Install `cmdk`

- [ ] **Step 1: Install**

```bash
cd /Users/tharusan/Projects/Decelerates/.worktrees/command-palette/frontend
npm install cmdk
```

- [ ] **Step 2: Commit**

```bash
cd /Users/tharusan/Projects/Decelerates/.worktrees/command-palette
git add frontend/package.json frontend/package-lock.json
git commit -m "chore(frontend): add cmdk dep for command palette"
```

### Task 2.2: Add shadcn `Command` primitive

**Files:**
- Create: `frontend/src/components/ui/command.tsx`

- [ ] **Step 1: Create the file**

This is the canonical shadcn Command component. Copy verbatim (source: https://ui.shadcn.com/docs/components/command):

```tsx
"use client";

import * as React from "react";
import { type DialogProps } from "@radix-ui/react-dialog";
import { Command as CommandPrimitive } from "cmdk";
import { Search } from "lucide-react";

import { cn } from "@/lib/cn";
import { Dialog, DialogContent } from "@/components/ui/dialog";

const Command = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive>
>(({ className, ...props }, ref) => (
  <CommandPrimitive
    ref={ref}
    className={cn(
      "flex h-full w-full flex-col overflow-hidden rounded-md bg-popover text-popover-foreground",
      className,
    )}
    {...props}
  />
));
Command.displayName = CommandPrimitive.displayName;

interface CommandDialogProps extends DialogProps {}

const CommandDialog = ({ children, ...props }: CommandDialogProps) => {
  return (
    <Dialog {...props}>
      <DialogContent className="overflow-hidden p-0 shadow-lg">
        <Command className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-muted-foreground [&_[cmdk-group]:not([hidden])_~[cmdk-group]]:pt-0 [&_[cmdk-group]]:px-2 [&_[cmdk-input-wrapper]_svg]:h-5 [&_[cmdk-input-wrapper]_svg]:w-5 [&_[cmdk-input]]:h-12 [&_[cmdk-item]]:px-2 [&_[cmdk-item]]:py-3 [&_[cmdk-item]_svg]:h-5 [&_[cmdk-item]_svg]:w-5">
          {children}
        </Command>
      </DialogContent>
    </Dialog>
  );
};

const CommandInput = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Input>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Input>
>(({ className, ...props }, ref) => (
  <div className="flex items-center border-b px-3" cmdk-input-wrapper="">
    <Search className="mr-2 h-4 w-4 shrink-0 opacity-50" />
    <CommandPrimitive.Input
      ref={ref}
      className={cn(
        "flex h-10 w-full rounded-md bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  </div>
));
CommandInput.displayName = CommandPrimitive.Input.displayName;

const CommandList = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.List>
>(({ className, ...props }, ref) => (
  <CommandPrimitive.List
    ref={ref}
    className={cn("max-h-[300px] overflow-y-auto overflow-x-hidden", className)}
    {...props}
  />
));
CommandList.displayName = CommandPrimitive.List.displayName;

const CommandEmpty = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Empty>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Empty>
>((props, ref) => (
  <CommandPrimitive.Empty
    ref={ref}
    className="py-6 text-center text-sm"
    {...props}
  />
));
CommandEmpty.displayName = CommandPrimitive.Empty.displayName;

const CommandGroup = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Group>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Group>
>(({ className, ...props }, ref) => (
  <CommandPrimitive.Group
    ref={ref}
    className={cn(
      "overflow-hidden p-1 text-foreground [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-muted-foreground",
      className,
    )}
    {...props}
  />
));
CommandGroup.displayName = CommandPrimitive.Group.displayName;

const CommandItem = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Item>
>(({ className, ...props }, ref) => (
  <CommandPrimitive.Item
    ref={ref}
    className={cn(
      "relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none aria-selected:bg-accent aria-selected:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
      className,
    )}
    {...props}
  />
));
CommandItem.displayName = CommandPrimitive.Item.displayName;

export {
  Command,
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
};
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend && npx tsc --noEmit
```
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ui/command.tsx
git commit -m "feat(frontend): add shadcn Command primitive"
```

### Task 2.3: Build the `CommandPalette` component

**Files:**
- Create: `frontend/src/components/command-palette.tsx`

The palette has two item groups:

1. **Routes** — 20 static route entries (map `/dashboard → "Dashboard"`, etc.) that open on Enter via `router.push()`.
2. **Selskaper** (companies) — debounced live search against the existing `/companies?q={term}` endpoint; on Enter, navigate to `/search/{orgnr}`.

- [ ] **Step 1: Write the component**

```tsx
"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  LayoutDashboard, Search as SearchIcon, Folder, BarChart3, RotateCcw,
  Kanban, BookOpen, FileSignature, ClipboardCheck, Building2,
  Lightbulb, UserPlus, ClipboardList, FileText, Video, BanknoteArrowUp,
  Shield, LogIn,
} from "lucide-react";

import {
  CommandDialog, CommandInput, CommandList, CommandGroup, CommandItem, CommandEmpty,
} from "@/components/ui/command";
import { getCompanies } from "@/lib/api";

type RouteItem = { href: string; label: string; icon: React.ReactNode };

const ROUTES: RouteItem[] = [
  { href: "/dashboard",           label: "Dashboard",               icon: <LayoutDashboard className="h-4 w-4" /> },
  { href: "/search",              label: "Søk",                      icon: <SearchIcon className="h-4 w-4" /> },
  { href: "/portfolio",           label: "Porteføljer",              icon: <Folder className="h-4 w-4" /> },
  { href: "/portfolio/analytics", label: "Porteføljeanalyse",        icon: <BarChart3 className="h-4 w-4" /> },
  { href: "/renewals",            label: "Fornyelser",               icon: <RotateCcw className="h-4 w-4" /> },
  { href: "/pipeline",            label: "Pipeline",                 icon: <Kanban className="h-4 w-4" /> },
  { href: "/knowledge",           label: "Kunnskapsbase",            icon: <BookOpen className="h-4 w-4" /> },
  { href: "/sla",                 label: "Tjenesteavtaler",          icon: <FileSignature className="h-4 w-4" /> },
  { href: "/idd",                 label: "IDD Behovsanalyse",        icon: <ClipboardCheck className="h-4 w-4" /> },
  { href: "/insurers",            label: "Forsikringsselskaper",     icon: <Building2 className="h-4 w-4" /> },
  { href: "/recommendations",     label: "Anbefalinger",             icon: <Lightbulb className="h-4 w-4" /> },
  { href: "/prospecting",         label: "Prospektering",            icon: <UserPlus className="h-4 w-4" /> },
  { href: "/tenders",             label: "Anbud",                    icon: <ClipboardList className="h-4 w-4" /> },
  { href: "/documents",           label: "Dokumenter",               icon: <FileText className="h-4 w-4" /> },
  { href: "/videos",              label: "Videoer",                  icon: <Video className="h-4 w-4" /> },
  { href: "/finans",              label: "Finans",                   icon: <BanknoteArrowUp className="h-4 w-4" /> },
  { href: "/admin",               label: "Admin",                    icon: <Shield className="h-4 w-4" /> },
  { href: "/login",               label: "Logg inn",                 icon: <LogIn className="h-4 w-4" /> },
];

interface CompanyHit {
  orgnr: string;
  navn?: string;
}

export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const [hits, setHits] = React.useState<CompanyHit[]>([]);
  const [loading, setLoading] = React.useState(false);

  // Global ⌘K / Ctrl+K keybind
  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  // Debounced company search
  React.useEffect(() => {
    if (!query || query.length < 2) {
      setHits([]);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const results = await getCompanies(10, "navn", { q: query });
        if (!controller.signal.aborted) {
          setHits(
            (results as CompanyHit[]).slice(0, 8).map((c) => ({
              orgnr: c.orgnr,
              navn: c.navn,
            })),
          );
        }
      } catch {
        if (!controller.signal.aborted) setHits([]);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, 200);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [query]);

  const go = React.useCallback(
    (href: string) => {
      setOpen(false);
      setQuery("");
      router.push(href);
    },
    [router],
  );

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput
        placeholder="Søk etter selskap eller side…"
        value={query}
        onValueChange={setQuery}
      />
      <CommandList>
        <CommandEmpty>
          {loading ? "Søker…" : "Ingen treff."}
        </CommandEmpty>

        {hits.length > 0 && (
          <CommandGroup heading="Selskaper">
            {hits.map((h) => (
              <CommandItem
                key={h.orgnr}
                value={`company-${h.orgnr}-${h.navn ?? ""}`}
                onSelect={() => go(`/search/${h.orgnr}`)}
              >
                <Building2 className="mr-2 h-4 w-4" />
                <span className="flex-1">{h.navn ?? h.orgnr}</span>
                <span className="text-xs text-muted-foreground">{h.orgnr}</span>
              </CommandItem>
            ))}
          </CommandGroup>
        )}

        <CommandGroup heading="Sider">
          {ROUTES.map((r) => (
            <CommandItem
              key={r.href}
              value={`route-${r.href}-${r.label}`}
              onSelect={() => go(r.href)}
            >
              <span className="mr-2">{r.icon}</span>
              <span>{r.label}</span>
              <span className="ml-auto text-xs text-muted-foreground">{r.href}</span>
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
```

**Important**: the `getCompanies` call uses the existing signature `getCompanies(limit, sortBy, filters)` from `frontend/src/lib/api.ts`. Verify that signature — if the real one requires the `q` filter differently, adjust accordingly. The TypeScript compiler will fail if the call is wrong; the fix is a one-line adjustment.

- [ ] **Step 2: Typecheck**

```bash
cd frontend && npx tsc --noEmit
```

If `getCompanies` doesn't accept `{ q }` as its filters object, open `frontend/src/lib/api.ts`, find `getCompanies`, check its actual parameter shape, and adjust the call above to match. Do NOT change `api.ts` — adjust the call site.

Expected after fix: clean.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/command-palette.tsx
git commit -m "feat(frontend): add CommandPalette with route shortcuts + company search"
```

### Task 2.4: Mount `CommandPalette` in AppShell

**Files:**
- Modify: `frontend/src/components/layout/AppShell.tsx`

- [ ] **Step 1: Import**

Add to the imports of `AppShell.tsx`:

```tsx
import { CommandPalette } from "@/components/command-palette";
```

- [ ] **Step 2: Render once near the root of AppShell**

Inside the outer `<div className="flex h-screen overflow-hidden">` (or whatever the root wrapper is), add `<CommandPalette />` as a sibling of the sidebar + main. Example:

```tsx
return (
  <div className="flex h-screen overflow-hidden">
    <CommandPalette />
    {/* existing sidebar and main content */}
    <aside>...</aside>
    <main>...</main>
  </div>
);
```

- [ ] **Step 3: Add a hint button in the header (optional polish)**

Next to `<ThemeToggle />` (from Phase 1), add a subtle button that opens the palette and shows the `⌘K` hint:

```tsx
<button
  onClick={() => {
    // dispatch a synthetic keydown to reuse the existing listener
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }));
  }}
  className="hidden md:inline-flex items-center gap-2 rounded-md border border-input bg-background px-3 py-1.5 text-xs text-muted-foreground hover:bg-accent"
  aria-label="Åpne kommandopalett"
>
  <Search className="h-3 w-3" />
  Søk…
  <kbd className="ml-2 rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium">⌘K</kbd>
</button>
```

If `Search` from `lucide-react` isn't already imported in AppShell, add it.

- [ ] **Step 4: Typecheck + lint + build**

```bash
cd frontend
npx tsc --noEmit && npm run lint && npm run build
```
Expected: clean.

- [ ] **Step 5: Manual smoke**

```bash
npm run dev
```

- Press `⌘K` (or `Ctrl+K`) on any page. Palette opens.
- Type `dash` → "Dashboard" highlights. Press Enter → navigates to `/dashboard`.
- Press `⌘K` again, type a company name (e.g., `DNB`) — after 200ms debounce, company hits appear. Click one → navigates to `/search/{orgnr}`.
- Press Escape while open → closes.
- Press `⌘K` while palette is already open → closes (toggle behavior).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/layout/AppShell.tsx
git commit -m "feat(frontend): mount CommandPalette + add ⌘K hint button in AppShell header"
```

### Task 2.5: Final verification + PR

- [ ] **Step 1: Full local CI**

```bash
cd /Users/tharusan/Projects/Decelerates/.worktrees/command-palette/frontend
npx tsc --noEmit && npm run lint && npm run build
npm run gen:api-types && git diff --exit-code src/lib/api-schema.ts
cd /Users/tharusan/Projects/Decelerates/.worktrees/command-palette
npx jscpd --ignore '**/__pycache__/**,**/.venv/**,**/node_modules/**,**/.git/**,uv.lock,**/.next/**,**/video/node_modules/**' --silent 2>&1 | tail -3
```

- [ ] **Step 2: Push + open PR**

```bash
git push -u origin feat/command-palette

gh pr create --base staging --title "feat(frontend): ⌘K command palette (routes + company search)" --body "$(cat <<'EOF'
## Summary

Phase 2 of the 2026-04-18 product UX expansion.

- Adds \`cmdk\` dep and the shadcn \`Command\` primitive under \`frontend/src/components/ui/\`.
- Adds \`CommandPalette\` that wraps \`CommandDialog\` with two groups:
  - **Sider** — 20 top-level routes with icons (navigate via \`router.push\`).
  - **Selskaper** — debounced live search against \`/companies?q=\` with a 200ms delay; picks navigate to \`/search/{orgnr}\`.
- Global keybind \`⌘K\` / \`Ctrl+K\` toggles open/closed.
- AppShell header gets a subtle \`Søk…\` button with \`⌘K\` kbd hint (hidden on mobile).

## Test plan

- [ ] Open palette from any route via \`⌘K\`.
- [ ] Type a route name — correct entry highlights and navigates on Enter.
- [ ] Type a company name — debounced search returns hits; Enter navigates to the company profile.
- [ ] Escape closes.
- [ ] Re-pressing \`⌘K\` while open closes.

## Out of scope

- Recent actions / history (adds stateful complexity, defer).
- Workflow actions (\"Create IDD\", \"Generate SLA\") — deferred.
- Document and video search — deferred.
EOF
)"
```

- [ ] **Step 3: Wait for CI, merge**

Same pattern as Phase 1 Task 1.8 Step 5.

### Done criteria — Phase 2

- `⌘K` opens a palette on every route.
- Route navigation works.
- Company search returns debounced hits.
- CI green; PR merged to staging.

---

# Phase 3 — User-facing accessibility preferences

**Goal:** Add a user-facing "Tilgjengelighet" (Accessibility) menu where users can: scale font size (3 presets), force reduced motion (regardless of OS), and enable a higher-contrast palette. Preferences persist per-device.

**Approach:** Pure CSS mechanism — attach `data-font-scale`, `data-reduced-motion`, `data-high-contrast` attributes to `<html>` via a small context/provider, and define CSS that reacts to those attributes. No new deps. Mount a small settings panel in the user-menu dropdown (or create a new gear icon in the header next to the ThemeToggle).

**File structure for Phase 3:**

- Create: `frontend/src/components/a11y/a11y-provider.tsx` — React context + localStorage persistence + effect that syncs preferences to `<html>` attributes.
- Create: `frontend/src/components/a11y/a11y-panel.tsx` — the dropdown UI with three controls.
- Modify: `frontend/src/app/globals.css` — CSS rules reacting to `html[data-font-scale]`, `html[data-reduced-motion]`, `html[data-high-contrast]`.
- Modify: `frontend/src/app/layout.tsx` — wrap in `<A11yProvider>` under `<ThemeProvider>`.
- Modify: `frontend/src/components/layout/AppShell.tsx` — render `<A11yPanel />` in the header.

### Task 3.1: CSS infrastructure

**Files:**
- Modify: `frontend/src/app/globals.css`

- [ ] **Step 1: Add the font-scale variable and rules**

Append to the end of `globals.css` (outside any layer):

```css
/* A11y preferences — font scale */
html {
  --font-scale: 1;
}
html[data-font-scale="large"]   { --font-scale: 1.125; }
html[data-font-scale="xlarge"]  { --font-scale: 1.25; }

body {
  font-size: calc(1rem * var(--font-scale));
}

/* A11y preferences — reduced motion override */
html[data-reduced-motion="true"] *,
html[data-reduced-motion="true"] *::before,
html[data-reduced-motion="true"] *::after {
  animation-duration: 0.01ms !important;
  animation-iteration-count: 1 !important;
  transition-duration: 0.01ms !important;
  scroll-behavior: auto !important;
}

/* A11y preferences — high contrast */
html[data-high-contrast="true"] {
  --background:      0 0% 100%;
  --foreground:      210 29% 10%;
  --muted-foreground: 210 29% 20%;
  --border:          210 29% 40%;
}
html[data-high-contrast="true"].dark {
  --background:      0 0% 4%;
  --foreground:      0 0% 98%;
  --muted-foreground: 0 0% 90%;
  --border:          0 0% 60%;
}

/* Also honor OS-level prefers-reduced-motion even without the toggle */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/tharusan/Projects/Decelerates/.worktrees/a11y-prefs
git add frontend/src/app/globals.css
git commit -m "feat(frontend): add CSS hooks for a11y preferences (font-scale, reduced-motion, high-contrast)"
```

### Task 3.2: `A11yProvider` context + localStorage persistence

**Files:**
- Create: `frontend/src/components/a11y/a11y-provider.tsx`

- [ ] **Step 1: Write the file**

```tsx
"use client";

import * as React from "react";

type FontScale = "default" | "large" | "xlarge";

interface A11yState {
  fontScale: FontScale;
  reducedMotion: boolean;
  highContrast: boolean;
}

interface A11yContextValue extends A11yState {
  setFontScale: (v: FontScale) => void;
  setReducedMotion: (v: boolean) => void;
  setHighContrast: (v: boolean) => void;
}

const A11yContext = React.createContext<A11yContextValue | null>(null);

const STORAGE_KEY = "a11y-prefs";

function loadInitial(): A11yState {
  if (typeof window === "undefined") {
    return { fontScale: "default", reducedMotion: false, highContrast: false };
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { fontScale: "default", reducedMotion: false, highContrast: false };
    const parsed = JSON.parse(raw) as Partial<A11yState>;
    return {
      fontScale: parsed.fontScale ?? "default",
      reducedMotion: parsed.reducedMotion ?? false,
      highContrast: parsed.highContrast ?? false,
    };
  } catch {
    return { fontScale: "default", reducedMotion: false, highContrast: false };
  }
}

export function A11yProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = React.useState<A11yState>(() => loadInitial());

  // Sync to <html> attributes
  React.useEffect(() => {
    const root = document.documentElement;
    if (state.fontScale === "default") root.removeAttribute("data-font-scale");
    else root.setAttribute("data-font-scale", state.fontScale);

    if (state.reducedMotion) root.setAttribute("data-reduced-motion", "true");
    else root.removeAttribute("data-reduced-motion");

    if (state.highContrast) root.setAttribute("data-high-contrast", "true");
    else root.removeAttribute("data-high-contrast");
  }, [state]);

  // Persist
  React.useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      // localStorage disabled — ignore
    }
  }, [state]);

  const value: A11yContextValue = {
    ...state,
    setFontScale: (fontScale) => setState((s) => ({ ...s, fontScale })),
    setReducedMotion: (reducedMotion) => setState((s) => ({ ...s, reducedMotion })),
    setHighContrast: (highContrast) => setState((s) => ({ ...s, highContrast })),
  };

  return <A11yContext.Provider value={value}>{children}</A11yContext.Provider>;
}

export function useA11y() {
  const ctx = React.useContext(A11yContext);
  if (!ctx) {
    throw new Error("useA11y must be used inside an A11yProvider");
  }
  return ctx;
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/a11y/a11y-provider.tsx
git commit -m "feat(frontend): add A11yProvider context with localStorage persistence"
```

### Task 3.3: `A11yPanel` dropdown

**Files:**
- Create: `frontend/src/components/a11y/a11y-panel.tsx`

- [ ] **Step 1: Write the file**

```tsx
"use client";

import * as React from "react";
import { Accessibility } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuCheckboxItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useA11y } from "@/components/a11y/a11y-provider";

export function A11yPanel() {
  const {
    fontScale, setFontScale,
    reducedMotion, setReducedMotion,
    highContrast, setHighContrast,
  } = useA11y();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Tilgjengelighet">
          <Accessibility className="h-4 w-4" />
          <span className="sr-only">Tilgjengelighet</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>Skriftstørrelse</DropdownMenuLabel>
        <DropdownMenuRadioGroup
          value={fontScale}
          onValueChange={(v) => setFontScale(v as typeof fontScale)}
        >
          <DropdownMenuRadioItem value="default">Normal</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="large">Stor</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="xlarge">Ekstra stor</DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>

        <DropdownMenuSeparator />

        <DropdownMenuCheckboxItem
          checked={reducedMotion}
          onCheckedChange={setReducedMotion}
        >
          Reduser animasjoner
        </DropdownMenuCheckboxItem>
        <DropdownMenuCheckboxItem
          checked={highContrast}
          onCheckedChange={setHighContrast}
        >
          Høy kontrast
        </DropdownMenuCheckboxItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
```

**Note**: verify that `DropdownMenuRadioGroup`, `DropdownMenuRadioItem`, and `DropdownMenuCheckboxItem` are exported from `frontend/src/components/ui/dropdown-menu.tsx`. If Tier 2's canonical shadcn install didn't include them, add them — they're one-liner re-exports from `@radix-ui/react-dropdown-menu`. Check the shadcn docs for the current canonical template: https://ui.shadcn.com/docs/components/dropdown-menu.

- [ ] **Step 2: Typecheck**

If missing exports, add them to `frontend/src/components/ui/dropdown-menu.tsx` — copy the Radio + Checkbox item forwardRefs directly from the shadcn canonical template.

```bash
cd frontend && npx tsc --noEmit
```
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/a11y/a11y-panel.tsx frontend/src/components/ui/dropdown-menu.tsx
git commit -m "feat(frontend): add A11yPanel dropdown (font-size / reduced-motion / high-contrast)"
```

### Task 3.4: Wire `A11yProvider` into layout + render `A11yPanel`

**Files:**
- Modify: `frontend/src/app/layout.tsx`
- Modify: `frontend/src/components/layout/AppShell.tsx`

- [ ] **Step 1: Add `<A11yProvider>` to layout**

In `frontend/src/app/layout.tsx`, import and wrap:

```tsx
import { A11yProvider } from "@/components/a11y/a11y-provider";
```

Then inside the tree, place `<A11yProvider>` as a child of `<ThemeProvider>` (so theme + a11y both wrap everything below):

```tsx
<ThemeProvider>
  <A11yProvider>
    <Providers>
      <LanguageProvider>
        <AppShell>
          <ErrorBoundary>{children}</ErrorBoundary>
        </AppShell>
      </LanguageProvider>
      <Toaster richColors closeButton position="top-right" />
    </Providers>
  </A11yProvider>
</ThemeProvider>
```

- [ ] **Step 2: Render `<A11yPanel>` in AppShell header**

In `frontend/src/components/layout/AppShell.tsx`, import and render it next to `<ThemeToggle>`:

```tsx
import { A11yPanel } from "@/components/a11y/a11y-panel";
```

In the header area:

```tsx
<div className="flex items-center gap-2">
  <A11yPanel />
  <ThemeToggle />
  {/* existing user menu, etc. */}
</div>
```

- [ ] **Step 3: Typecheck + lint + build**

```bash
cd frontend
npx tsc --noEmit && npm run lint && npm run build
```
Expected: clean.

- [ ] **Step 4: Manual smoke**

```bash
npm run dev
```

- Click the accessibility icon. Panel opens.
- Select "Stor" (large) — body text everywhere scales up 12.5%. Select "Ekstra stor" — 25%. Back to "Normal" — 1:1.
- Toggle "Reduser animasjoner" — hover transitions and spinners no longer animate.
- Toggle "Høy kontrast" — text/background contrast increases visibly. Works in both light and dark theme.
- Refresh the page — all three preferences persist.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/layout.tsx frontend/src/components/layout/AppShell.tsx
git commit -m "feat(frontend): wire A11yProvider + render A11yPanel in AppShell"
```

### Task 3.5: Final verification + PR

- [ ] **Step 1: Full local CI + push + PR**

Same pattern as Phase 1 Task 1.8. PR title: `feat(frontend): user-facing a11y preferences (font-scale, reduced-motion, high-contrast)`.

PR body should include:

```markdown
## Summary

Phase 3 of the 2026-04-18 product UX expansion.

- Adds `A11yProvider` context storing `fontScale`, `reducedMotion`, `highContrast` in localStorage.
- Adds `A11yPanel` dropdown in AppShell header.
- CSS hooks via `data-font-scale`, `data-reduced-motion`, `data-high-contrast` on `<html>`.
- Also respects OS-level `prefers-reduced-motion` independently of the toggle.

## Test plan
- [ ] Font-scale dropdown changes body text size on every route.
- [ ] Reduced-motion toggle disables animations.
- [ ] High-contrast toggle increases contrast in both light and dark theme.
- [ ] All preferences persist across refresh.

## Out of scope
- Keyboard shortcut cheat-sheet overlay.
- Reading-guide ruler.
- Voice input.
```

- [ ] **Step 2: Merge via script**

Same pattern as Phase 1.

### Done criteria — Phase 3

- `A11yPanel` accessible from every route.
- All three preferences visibly affect rendering.
- Preferences persist.
- CI green; PR merged to staging.

---

# Phase 4 — i18n activation (Norwegian ↔ English)

**Goal:** Users can switch between Norwegian and English in the user menu; the choice persists; the app's shell (sidebar labels, page titles, main headings) renders in the chosen language. Deep-page strings (IDD form helpers, SLA wizard step descriptions, etc.) stay Norwegian for now — a follow-up issue tracks the full sweep.

**Approach:** The i18n infrastructure already exists at `frontend/src/lib/i18n.tsx`:

- `LanguageProvider` wraps the app in root layout.
- `useT()` hook + `T("key")` returns the translated string.
- `translations.json` has 100+ populated NO/EN keys.

**But `useT()` is called in exactly 1 file across the codebase.** This phase:

1. Extends the provider to read/write locale via `localStorage` and sync `<html lang>`.
2. Adds a locale switcher to the user menu.
3. Sweeps **AppShell navigation labels** (20 routes), **dashboard page** (`frontend/src/app/dashboard/page.tsx`), and **the 4 main page headings** on `/search`, `/portfolio`, `/renewals`, `/knowledge` to actually call `T()`.

Everything else stays Norwegian (the existing product language). Users who switch to English will see a mixed UI — the shell + entry pages in English, deeper flows in Norwegian. That's fine for this phase and is called out in the release notes.

**File structure for Phase 4:**

- Modify: `frontend/src/lib/i18n.tsx` — add localStorage persistence; sync `document.documentElement.lang`.
- Modify: `frontend/translations.json` — add any missing keys that the shell + entry pages need.
- Create: `frontend/src/components/locale-switcher.tsx` — NO/EN dropdown.
- Modify: `frontend/src/components/layout/AppShell.tsx` — swap 20 nav labels to `T()`; render `<LocaleSwitcher />`.
- Modify: `frontend/src/app/dashboard/page.tsx` — swap hardcoded strings to `T()`.
- Modify: `frontend/src/app/search/page.tsx`, `frontend/src/app/portfolio/page.tsx`, `frontend/src/app/renewals/page.tsx`, `frontend/src/app/knowledge/page.tsx` — swap top-of-page headings to `T()`.

### Task 4.1: Extend `LanguageProvider` with persistence

**Files:**
- Modify: `frontend/src/lib/i18n.tsx`

- [ ] **Step 1: Rewrite the provider body**

Replace the existing provider body with:

```tsx
"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  type ReactNode,
} from "react";
import translations from "@/../translations.json";

type Lang = "no" | "en";
type Translations = Record<string, { no?: string; en?: string }>;

const _t = translations as Translations;
const STORAGE_KEY = "app-lang";

interface I18nContextValue {
  lang: Lang;
  setLang: (l: Lang) => void;
  T: (key: string) => string;
}

const I18nContext = createContext<I18nContextValue>({
  lang: "no",
  setLang: () => undefined,
  T: (k) => k,
});

function loadInitial(): Lang {
  if (typeof window === "undefined") return "no";
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw === "no" || raw === "en") return raw;
  } catch {
    /* ignored */
  }
  return "no";
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => loadInitial());

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      window.localStorage.setItem(STORAGE_KEY, l);
    } catch {
      /* ignored */
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const T = useCallback(
    (key: string): string => {
      const entry = _t[key];
      if (!entry) return key;
      return entry[lang] ?? entry.en ?? key;
    },
    [lang],
  );

  return (
    <I18nContext.Provider value={{ lang, setLang, T }}>
      {children}
    </I18nContext.Provider>
  );
}

export const useI18n = () => useContext(I18nContext);
export const useT = () => useContext(I18nContext).T;
```

Key changes: localStorage read on mount, localStorage write on `setLang`, effect that syncs `document.documentElement.lang` to the current value.

- [ ] **Step 2: Typecheck**

```bash
cd frontend && npx tsc --noEmit
```
Expected: clean.

- [ ] **Step 3: Commit**

```bash
cd /Users/tharusan/Projects/Decelerates/.worktrees/i18n-activation
git add frontend/src/lib/i18n.tsx
git commit -m "feat(frontend): i18n persistence + <html lang> sync"
```

### Task 4.2: Add locale switcher

**Files:**
- Create: `frontend/src/components/locale-switcher.tsx`

- [ ] **Step 1: Write the component**

```tsx
"use client";

import { Languages } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useI18n } from "@/lib/i18n";

export function LocaleSwitcher() {
  const { lang, setLang } = useI18n();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" aria-label="Språk">
          <Languages className="mr-2 h-4 w-4" />
          <span className="text-xs uppercase">{lang}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => setLang("no")}>Norsk</DropdownMenuItem>
        <DropdownMenuItem onClick={() => setLang("en")}>English</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/locale-switcher.tsx
git commit -m "feat(frontend): add LocaleSwitcher (NO/EN)"
```

### Task 4.3: Populate missing translations

**Files:**
- Modify: `frontend/translations.json`

Before swapping the strings, verify that every string we're about to translate has a key in `translations.json`. If missing, add it.

- [ ] **Step 1: Enumerate strings we'll swap**

AppShell nav labels (from the `NAV_ITEMS` array in AppShell.tsx — read it to get exact strings). Likely values:

- Hjem / Home
- Søk / Search
- Portefølje / Portfolio
- Fornyelser / Renewals
- Pipeline / Pipeline
- Kunnskap / Knowledge
- Tjenesteavtaler / Service agreements
- IDD / IDD
- Forsikringsselskaper / Insurers
- Anbefalinger / Recommendations
- Prospektering / Prospecting
- Anbud / Tenders
- Dokumenter / Documents
- Videoer / Videos
- Finans / Finance
- Admin / Admin
- Logg inn / Log in

Dashboard page headings:
- Velkommen / Welcome
- Fornyelser neste 30 dager / Renewals next 30 days
- Aktive avtaler / Active agreements
- Åpne skader / Open claims
- Aktiviteter forfalt / Overdue activities

Search / Portfolio / Renewals / Knowledge page titles:
- Selskapssøk / Company search
- Porteføljer / Portfolios
- Kommende fornyelser / Upcoming renewals
- Kunnskapsbase / Knowledge base

Chat/onboarding strings inside dashboard (if any).

- [ ] **Step 2: For each string, check `translations.json`**

```bash
grep -c '"Hjem"\|"Søk"\|"Portefølje"\|"Fornyelser"\|"Pipeline"\|"Kunnskap"\|"Velkommen"' frontend/translations.json
```

If the count is low (< 20), most entries are missing. Open `translations.json` and add any missing keys. Keep the existing ones.

Example entries to add (skip if already present — check before adding):

```json
{
  "Hjem": { "no": "Hjem", "en": "Home" },
  "Søk": { "no": "Søk", "en": "Search" },
  "Portefølje": { "no": "Portefølje", "en": "Portfolio" },
  "Fornyelser": { "no": "Fornyelser", "en": "Renewals" },
  "Pipeline": { "no": "Pipeline", "en": "Pipeline" },
  "Kunnskap": { "no": "Kunnskap", "en": "Knowledge" },
  "Tjenesteavtaler": { "no": "Tjenesteavtaler", "en": "Service agreements" },
  "IDD": { "no": "IDD", "en": "IDD" },
  "Forsikringsselskaper": { "no": "Forsikringsselskaper", "en": "Insurers" },
  "Anbefalinger": { "no": "Anbefalinger", "en": "Recommendations" },
  "Prospektering": { "no": "Prospektering", "en": "Prospecting" },
  "Anbud": { "no": "Anbud", "en": "Tenders" },
  "Dokumenter": { "no": "Dokumenter", "en": "Documents" },
  "Videoer": { "no": "Videoer", "en": "Videos" },
  "Finans": { "no": "Finans", "en": "Finance" },
  "Admin": { "no": "Admin", "en": "Admin" },
  "Logg inn": { "no": "Logg inn", "en": "Log in" },
  "Velkommen": { "no": "Velkommen", "en": "Welcome" },
  "Fornyelser neste 30 dager": { "no": "Fornyelser neste 30 dager", "en": "Renewals next 30 days" },
  "Aktive avtaler": { "no": "Aktive avtaler", "en": "Active agreements" },
  "Åpne skader": { "no": "Åpne skader", "en": "Open claims" },
  "Aktiviteter forfalt": { "no": "Aktiviteter forfalt", "en": "Overdue activities" },
  "Selskapssøk": { "no": "Selskapssøk", "en": "Company search" },
  "Porteføljer": { "no": "Porteføljer", "en": "Portfolios" },
  "Kommende fornyelser": { "no": "Kommende fornyelser", "en": "Upcoming renewals" },
  "Kunnskapsbase": { "no": "Kunnskapsbase", "en": "Knowledge base" }
}
```

- [ ] **Step 3: Validate JSON**

```bash
node -e "JSON.parse(require('fs').readFileSync('frontend/translations.json', 'utf8'))"
```
Expected: no output (parses OK).

- [ ] **Step 4: Commit**

```bash
git add frontend/translations.json
git commit -m "feat(frontend): populate translations.json for shell + entry pages (i18n)"
```

### Task 4.4: Swap shell + entry-page strings to `T()`

**Files:**
- Modify: `frontend/src/components/layout/AppShell.tsx`
- Modify: `frontend/src/app/dashboard/page.tsx`
- Modify: `frontend/src/app/search/page.tsx`
- Modify: `frontend/src/app/portfolio/page.tsx`
- Modify: `frontend/src/app/renewals/page.tsx`
- Modify: `frontend/src/app/knowledge/page.tsx`

- [ ] **Step 1: AppShell navigation labels**

In `frontend/src/components/layout/AppShell.tsx`:

1. Add import: `import { useT } from "@/lib/i18n";`
2. Inside the component body: `const T = useT();`
3. Replace each hardcoded nav label with `T("...")`. Example:

```tsx
{NAV_ITEMS.map(({ href, label, icon: Icon }) => {
  const isActive = pathname.startsWith(href);
  return (
    <Link ... aria-current={isActive ? "page" : undefined} className={...}>
      <Icon className="..." />
      {T(label)}   {/* was: {label} */}
    </Link>
  );
})}
```

Note: the `label` field in `NAV_ITEMS` is the key — it must match an entry in `translations.json`. Verify the values in `NAV_ITEMS` match the keys you added in Task 4.3.

- [ ] **Step 2: Render `<LocaleSwitcher>` in header**

Add import:

```tsx
import { LocaleSwitcher } from "@/components/locale-switcher";
```

In the header (next to `<A11yPanel />` and `<ThemeToggle />` from previous phases):

```tsx
<div className="flex items-center gap-2">
  <LocaleSwitcher />
  <A11yPanel />
  <ThemeToggle />
</div>
```

- [ ] **Step 3: Dashboard strings**

In `frontend/src/app/dashboard/page.tsx`:

1. Add `useT` import and `const T = useT();`.
2. Replace the 5 strings identified in Task 4.3 Step 1 (Dashboard page) with `T("...")`.

Example:

```tsx
<h1 className="...">{T("Velkommen")}</h1>
// ...
<MetricCard label={T("Fornyelser neste 30 dager")} ... />
<MetricCard label={T("Aktive avtaler")} ... />
<MetricCard label={T("Åpne skader")} ... />
<MetricCard label={T("Aktiviteter forfalt")} ... />
```

- [ ] **Step 4: Other entry-page titles**

For each of `search/page.tsx`, `portfolio/page.tsx`, `renewals/page.tsx`, `knowledge/page.tsx`:

1. Add the `useT` import and `const T = useT();`.
2. Replace ONLY the top heading / title text with `T("...")`. Leave the rest of the page strings in Norwegian for this phase.

Example (for search/page.tsx):

```tsx
<h1 className="...">{T("Selskapssøk")}</h1>
```

- [ ] **Step 5: Typecheck + lint + build**

```bash
cd frontend
npx tsc --noEmit && npm run lint && npm run build
```
Expected: clean.

- [ ] **Step 6: Manual smoke**

```bash
npm run dev
```

- Click the languages icon → choose "English". The sidebar flips to English (Home / Search / Portfolio / Renewals / …). Dashboard page flips to English. Switch back — everything flips back.
- Visit `/search`, `/portfolio`, `/renewals`, `/knowledge`. Each top heading flips with the language.
- Refresh the page. Locale persists.
- Inspect `<html>` in devtools — `lang` attribute switches between `no` and `en`.
- Enter a deep page (`/sla`, `/idd`, `/pipeline`). These stay Norwegian — that's expected for this phase.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/layout/AppShell.tsx frontend/src/app/dashboard/page.tsx frontend/src/app/search/page.tsx frontend/src/app/portfolio/page.tsx frontend/src/app/renewals/page.tsx frontend/src/app/knowledge/page.tsx
git commit -m "feat(frontend): swap shell + entry-page strings to T() calls (i18n)"
```

### Task 4.5: File a follow-up issue for the rest of the sweep

Tier 4's remaining scope (the other ~15 routes, deep flows, error messages, etc.) is a multi-day sweep. File it explicitly:

- [ ] **Step 1: Create the issue**

```bash
gh issue create --title "chore(frontend): complete i18n sweep — deep flows (IDD, SLA, pipeline, etc.)" --body "$(cat <<'EOF'
## Summary

Phase 4 of the 2026-04-18 product UX expansion activated the existing i18n infrastructure and swept AppShell + dashboard + 4 entry-page titles to use \`T()\`. The rest of the app's UI strings remain hardcoded Norwegian. Users who switch to English see a mixed UI: shell + entry pages in English, deep flows in Norwegian.

## What's left

| Route / Component | Estimated string count |
|--- |---|
| \`/search/[orgnr]\` — 6 tabs + all subsections | 100-150 |
| \`/portfolio/[id]\` + portfolio analytics | 60-80 |
| \`/pipeline\` — columns, labels, deal card, modal | 30-40 |
| \`/sla\` wizard (5 steps) | 80-100 |
| \`/idd\` form | 50-60 |
| \`/knowledge\` sub-tabs + chat | 30-40 |
| \`/prospecting\` + \`/insurers\` + \`/recommendations\` + \`/tenders\` | 80-100 |
| \`/admin\` | 30-40 |
| Error messages + toast strings | 40-60 |
| ConfirmDialog / Dialog contents | 20-30 |

Total: ~500-700 strings across ~20 routes.

## Approach

- Prefer sweeping one route at a time, each as its own PR.
- For each new \`T(\"...\")\` call, ensure the key is populated in \`frontend/translations.json\` with both \`no\` and \`en\` values.
- Consider \`scripts/find-untranslated-strings.js\` (would be a new helper) that walks \`.tsx\` files and flags Norwegian-looking string literals not wrapped in \`T()\`.

## Acceptance

- \`grep -rE '>[A-ZÆØÅ][a-zæøå]' frontend/src/app\` (rough Norwegian-string heuristic) returns zero un-wrapped hits.
- Manual: switch to English on every route; no Norwegian strings remain in the UI.

## Out of scope

- Adding more languages (German, Swedish, etc.).
- Server-side i18n (backend error messages remain Norwegian per product language).
EOF
)" --label "enhancement"
```

Capture the new issue number and reference it in the PR description.

### Task 4.6: Final verification + PR

- [ ] **Step 1: Full local CI**

```bash
cd /Users/tharusan/Projects/Decelerates/.worktrees/i18n-activation/frontend
npx tsc --noEmit && npm run lint && npm run build
npm run gen:api-types && git diff --exit-code src/lib/api-schema.ts
cd /Users/tharusan/Projects/Decelerates/.worktrees/i18n-activation
npx jscpd --ignore '**/__pycache__/**,**/.venv/**,**/node_modules/**,**/.git/**,uv.lock,**/.next/**,**/video/node_modules/**' --silent 2>&1 | tail -3
```

- [ ] **Step 2: Push + open PR**

```bash
git push -u origin feat/i18n-activation

gh pr create --base staging --title "feat(frontend): i18n activation — locale switcher + shell/entry-page sweep" --body "$(cat <<'EOF'
## Summary

Phase 4 of the 2026-04-18 product UX expansion. Activates the i18n infrastructure that has been sitting unused since its commit (\`translations.json\` + \`LanguageProvider\` context + \`useT()\` hook — all in place, but previously called by zero UI files).

- Extends \`LanguageProvider\` with localStorage persistence and \`<html lang>\` sync.
- Adds \`LocaleSwitcher\` (NO / EN dropdown) to AppShell header.
- Sweeps AppShell navigation labels (20 routes), Dashboard page, and 4 entry-page headings (\`/search\`, \`/portfolio\`, \`/renewals\`, \`/knowledge\`) to call \`T()\`.
- Populates ~25 additional keys in \`translations.json\` for the shell/entry sweep.

## Mixed-UI warning

Users who switch to English will see English in the shell + entry pages but Norwegian in deep flows (IDD, SLA wizard, pipeline, admin, etc.). Full sweep tracked in issue #<FILL_IN_FROM_TASK_4.5>.

## Test plan

- [ ] Sidebar + header flip NO ↔ EN when the switcher changes.
- [ ] Dashboard + 4 entry-page titles flip.
- [ ] \`<html lang>\` matches the active locale.
- [ ] Refresh → locale persists.
- [ ] Deep flows (SLA, IDD, pipeline) stay Norwegian (expected; not a regression).

## Out of scope

- Backend error messages / toast strings.
- Deep-flow sweep (tracked in follow-up issue).
EOF
)"
```

Replace `<FILL_IN_FROM_TASK_4.5>` with the actual issue number.

- [ ] **Step 3: Merge via script**

Same pattern as Phase 1 Task 1.8 Step 5.

### Done criteria — Phase 4

- `LocaleSwitcher` flips shell + entry pages between NO and EN.
- `<html lang>` tracks the active locale.
- Locale persists to localStorage.
- Follow-up issue filed for the full sweep.
- CI green; PR merged to staging.

---

## Full rollout ordering

The four phases are independent (no cross-dependencies). Recommended order:

1. **Phase 1 — Dark mode** (earliest user-visible win; leverages Tier 2 tokens).
2. **Phase 2 — Command palette** (highest daily-productivity ROI for brokers).
3. **Phase 3 — A11y preferences** (complements dark mode since high-contrast extends the theme system).
4. **Phase 4 — i18n activation** (most scope-sensitive; saved for last because the remaining strings are a long-tail follow-up).

Each phase ships as its own PR to `staging`, then a promotion PR from `staging` to `main`. Expect ~1-2 days per phase for execution plus the merge-and-deploy cycle.

## Out of scope (explicit)

- **Onboarding tour redesign** — the existing OnboardingTour works and is orthogonal to these changes.
- **Mobile responsive pass** — separate initiative (U14 in the 2026-04-17 audit).
- **Performance / bundle-size work** — separate profiling pass.
- **Server-side i18n** — backend error messages remain Norwegian as a product decision.
- **Additional locales** beyond NO/EN — bring to product before building.
- **Voice input / screen-reader beyond WCAG 2.1 AA** — the axe gate already covers the compliance baseline; extra tooling belongs to a separate a11y initiative if broker feedback warrants it.
