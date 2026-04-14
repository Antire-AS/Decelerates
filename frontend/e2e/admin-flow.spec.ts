import { test, expect } from "@playwright/test";

/**
 * Admin flow — admin panel with system stats, data controls, and exports.
 *
 * The /admin page renders several sections:
 * - System stats grid (Selskaper, Aktive avtaler, Dokumenter, etc.)
 * - Users management (UsersSection)
 * - Exports (ExportsSection) — Excel download buttons
 * - Data controls — seed buttons, demo data, reset
 * - Audit log (AuditLogSection)
 *
 * These tests are read-only: they verify the UI renders but do NOT click
 * destructive buttons (seed, reset) because those mutate staging data.
 */

test.describe("Admin", () => {
  test("page renders heading and stats grid", async ({ page }) => {
    await page.goto("/admin");
    await expect(page.getByRole("heading", { name: /Admin/i })).toBeVisible({ timeout: 30_000 });
    // The description text under the heading.
    await expect(page.getByText(/Systemstatistikk/i).first()).toBeVisible();
    // Stats grid should show at least one stat label from STAT_LABELS.
    const statLabel = page.locator("text=/Selskaper|Aktive avtaler|Dokumenter/i").first();
    await expect(statLabel).toBeVisible({ timeout: 30_000 });
  });

  test("seed buttons are visible in data controls", async ({ page }) => {
    await page.goto("/admin");
    await expect(page.getByRole("heading", { name: /Admin/i })).toBeVisible({ timeout: 30_000 });
    // Scroll to data controls section — seed buttons should be visible.
    await expect(
      page.getByText("Seed fiktive selskaper (full demo)").first()
    ).toBeVisible({ timeout: 30_000 });
    await expect(
      page.getByText("Seed CRM demo-data").first()
    ).toBeVisible();
  });

  test("export section shows Excel download buttons", async ({ page }) => {
    await page.goto("/admin");
    await expect(page.getByRole("heading", { name: /Admin/i })).toBeVisible({ timeout: 30_000 });
    // The ExportsSection renders under "Eksporter data" heading.
    await expect(page.getByText("Eksporter data").first()).toBeVisible({ timeout: 30_000 });
    // Two Excel export buttons.
    await expect(page.getByText("Fornyelsesrapport (Excel)").first()).toBeVisible();
    await expect(page.getByText("Avtaleoversikt (Excel)").first()).toBeVisible();
  });
});
