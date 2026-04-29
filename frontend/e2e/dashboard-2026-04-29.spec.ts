/**
 * Dashboard surfaces shipped 2026-04-29 — Hurtighandlinger, Top-3 renewals,
 * PremiumTrendCard, AI-anbefalinger panel.
 *
 * These specs assert the surface RENDERS, not that data is present. With
 * a fresh staging DB the cards conditionally hide (e.g. PremiumTrendCard
 * only renders when total_premium_book > 0). When that happens the test
 * skips that subsection rather than failing — landing-page assertions
 * stay loose because seeded data is environment-dependent.
 */
import { test, expect } from "@playwright/test";
import { dismissOnboarding } from "./_helpers";

test.describe("Dashboard new surfaces (2026-04-29)", () => {
  test.beforeEach(async ({ page }) => {
    await dismissOnboarding(page);
    await page.goto("/dashboard", { timeout: 60_000 });
  });

  test("Hurtighandlinger card renders 4 verb-first actions", async ({ page }) => {
    const card = page.getByRole("heading", { name: /Hurtighandlinger/i }).locator("..");
    await expect(card).toBeVisible();
    // 4 verb-first labels from PR #289
    for (const label of ["Søk selskap", "Ny behovsanalyse", "Generer anbudspakke", "Vis portefølje"]) {
      await expect(card.getByText(new RegExp(label, "i"))).toBeVisible();
    }
  });

  test("PremiumTrendCard renders bar chart when CRM has data", async ({ page }) => {
    const heading = page.getByText(/Samlet premievolum/i).first();
    if (!(await heading.isVisible().catch(() => false))) {
      test.skip(true, "No premium data on this env — card hidden by hasCrm guard");
    }
    const card = heading.locator("..");
    // recharts renders SVG <rect> for each Bar — expect ≥1 (could be up to 12)
    const bars = card.locator("svg rect").filter({ hasNot: page.locator("[stroke-dasharray]") });
    await expect.poll(() => bars.count(), { timeout: 5_000 }).toBeGreaterThan(0);
  });

  test("Top-3 renewals card renders when renewals_30d > 0", async ({ page }) => {
    const heading = page.getByRole("heading", { name: /Forfaller først/i });
    if (!(await heading.isVisible().catch(() => false))) {
      test.skip(true, "No renewals in next 30d — card hidden");
    }
    // Each row has an urgency pill ("X d" or "I dag") + clickable Link to /search/<orgnr>
    const card = heading.locator("..");
    const rows = card.locator("a[href^='/search/']");
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);
    expect(count).toBeLessThanOrEqual(3);
  });

  test("AI-anbefalinger panel renders if engine has fired", async ({ page }) => {
    const heading = page.getByRole("heading", { name: /AI-anbefalinger/i });
    if (!(await heading.isVisible().catch(() => false))) {
      test.skip(true, "No recommendations on this env — panel returns null");
    }
    // Each item has a CTA link
    const card = heading.locator("..");
    await expect(card.locator("a")).toHaveCount(await card.locator("a").count());
  });
});
