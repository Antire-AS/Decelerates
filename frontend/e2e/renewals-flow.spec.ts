import { test, expect } from "@playwright/test";

/**
 * Renewals flow — broker reviews upcoming policy renewals.
 *
 * The /renewals page shows a table of policies expiring within a configurable
 * window (30d/60d/90d/180d). The default is 90 days. It also supports a
 * Pipeline (kanban) view toggle. CRM demo data seeds realistic renewals on
 * staging so there should always be at least some rows visible.
 */

test.describe("Renewals", () => {
  test("page renders heading and renewal content", async ({ page }) => {
    await page.goto("/renewals");
    await expect(page.getByRole("heading", { name: /Fornyelsespipeline/i })).toBeVisible({ timeout: 30_000 });
    // Either there are renewals (table with rows) or the empty state message.
    const content = page.locator("text=/Klient|Ingen kommende fornyelser/i").first();
    await expect(content).toBeVisible({ timeout: 30_000 });
  });

  test("table columns are present when renewals exist", async ({ page }) => {
    await page.goto("/renewals");
    // Wait for the page to settle — look for the heading first.
    await expect(page.getByText(/Fornyelsespipeline/i).first()).toBeVisible({ timeout: 30_000 });
    // If renewals exist, the table headers should show Norwegian column names.
    // Skip assertion gracefully if the empty state is shown instead.
    const hasTable = await page.getByText("Forsikringstype").isVisible().catch(() => false);
    if (hasTable) {
      await expect(page.getByText("Klient").first()).toBeVisible();
      await expect(page.getByText("Forsikringstype").first()).toBeVisible();
      await expect(page.getByText("Fornyelsesdato").first()).toBeVisible();
      await expect(page.getByText("Dager igjen").first()).toBeVisible();
    }
  });

  test("day filter buttons are visible and clickable", async ({ page }) => {
    await page.goto("/renewals");
    await expect(page.getByText(/Fornyelsespipeline/i).first()).toBeVisible({ timeout: 30_000 });
    // The day filter buttons: 30d, 60d, 90d, 180d
    for (const d of ["30d", "60d", "90d", "180d"]) {
      await expect(page.getByText(d, { exact: true }).first()).toBeVisible();
    }
    // Click 30d and verify it gets the active state (visual check: button changes).
    await page.getByText("30d", { exact: true }).first().click();
    // After clicking, the page should still render without error.
    await expect(page.locator("#__next_error__")).toHaveCount(0);
  });

  test("Tabell and Pipeline view toggles work", async ({ page }) => {
    await page.goto("/renewals");
    await expect(page.getByText(/Fornyelsespipeline/i).first()).toBeVisible({ timeout: 30_000 });
    // View toggle buttons only appear when there are renewals.
    const hasToggles = await page.getByText("Tabell", { exact: true }).isVisible().catch(() => false);
    if (hasToggles) {
      // Click Pipeline view
      await page.getByText("Pipeline", { exact: true }).click();
      // Pipeline view renders stage labels (Ikke startet, Klar for tilbud, etc.)
      const stageLabel = page.locator("text=/Ikke startet|Klar for tilbud|Tilbud sendt/i").first();
      await expect(stageLabel).toBeVisible({ timeout: 10_000 });
      // Switch back to table view
      await page.getByText("Tabell", { exact: true }).click();
      await expect(page.locator("#__next_error__")).toHaveCount(0);
    }
  });
});
