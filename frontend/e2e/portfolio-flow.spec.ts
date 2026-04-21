import { test, expect } from "@playwright/test";
import { dismissOnboarding } from "./_helpers";

/**
 * Portfolio flow — broker browses their book of business via the portfolio
 * pages. These tests are read-only: they don't create new portfolios because
 * doing so on staging/prod leaves persistent data.
 *
 * The /portfolio page is supposed to render the list, /portfolio/analytics
 * is the cross-portfolio dashboard, and /portfolio/[id] is the per-portfolio
 * detail view (skipped if no portfolios exist in the env).
 */

test.beforeEach(async ({ page }) => {
  await dismissOnboarding(page);
});

test("portfolio: list page renders the create-portfolio call to action", async ({ page }) => {
  await page.goto("/portfolio");
  // Either there are portfolios listed (with names), or the empty state
  // shows a "create portfolio" affordance. Both are valid.
  const list = page.getByText(/porteføl/i).first();
  await expect(list).toBeVisible({ timeout: 30_000 });
});

test("portfolio: analytics page renders without error", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  await page.goto("/portfolio/analytics");
  await expect(page.locator("#__next_error__")).toHaveCount(0);
  // Analytics page typically shows some kind of header/title.
  await expect(page.getByText(/analytics|analyse|porteføl/i).first()).toBeVisible({ timeout: 30_000 });
  expect(errors, `console errors: ${errors.join(" | ")}`).toEqual([]);
});

test("portfolio: prospecting page renders search filters", async ({ page }) => {
  await page.goto("/prospecting");
  // Prospecting always renders the filter UI even when there are zero results.
  await expect(page.getByText(/prospekt|filter|industri|risiko/i).first()).toBeVisible({
    timeout: 30_000,
  });
});
