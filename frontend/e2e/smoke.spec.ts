import { test, expect } from "@playwright/test";
import { dismissOnboarding } from "./_helpers";

/**
 * Smoke tests — every top-level broker page must render without throwing.
 *
 * These are the lowest-value-but-fastest tests in the suite. They catch the
 * "I shipped a broken React component" class of bug before it reaches a
 * broker. They do NOT verify business logic — that's what the flow specs
 * below are for.
 *
 * Each test:
 *   1. Loads the page with a 60s navigation timeout
 *   2. Asserts the response was a 2xx (3xx are also OK — auth-disabled
 *      `/login` 307s to `/dashboard`, prod-mode redirects can do that too)
 *   3. Asserts no Next.js error boundary appeared
 *   4. Asserts a page-specific landmark element is visible
 */

// Note: /recommendations is intentionally omitted — it's a redirect alias
// to /search?tab=crm and renders no UI of its own (see
// frontend/src/app/recommendations/page.tsx).
const PAGES: Array<{ path: string; landmark: RegExp | string }> = [
  { path: "/dashboard",       landmark: /Velkommen/i },
  { path: "/search",          landmark: /selskapsøk/i },
  { path: "/portfolio",       landmark: /porteføl/i },
  { path: "/renewals",        landmark: /fornyel/i },
  { path: "/knowledge",       landmark: /kunnskap/i },
  { path: "/insurers",        landmark: /forsikringssel/i },
  { path: "/prospecting",     landmark: /prospekt/i },
];

test.beforeEach(async ({ page }) => {
  await dismissOnboarding(page);
});

for (const { path, landmark } of PAGES) {
  test(`smoke: ${path} renders`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));

    const response = await page.goto(path);
    expect(response, `no response for ${path}`).not.toBeNull();
    expect(response!.status(), `bad status for ${path}`).toBeLessThan(400);

    // Next.js error boundary uses this id when a render fails.
    await expect(page.locator("#__next_error__")).toHaveCount(0);

    // Landmark text confirms the page actually rendered Norwegian content,
    // not just an empty shell.
    await expect(page.getByText(landmark).first()).toBeVisible({ timeout: 30_000 });

    expect(errors, `console pageerrors on ${path}: ${errors.join(" | ")}`).toEqual([]);
  });
}
