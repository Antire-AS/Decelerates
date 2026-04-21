import { test, expect } from "@playwright/test";
import { dismissOnboarding } from "./_helpers";

/**
 * IDD + Insurers + SLA flow — broker uses compliance and configuration pages.
 *
 * /idd — IDD behovsanalyse list (firm-wide when no orgnr query param)
 * /insurers — insurer registry with product appetite
 * /sla — SLA agreement wizard with 3 tabs: Ny avtale, Mine avtaler, Meglerinnstillinger
 */

test.describe("IDD, Insurers, and SLA", () => {
  test.beforeEach(async ({ page }) => {
    await dismissOnboarding(page);
  });

  test("IDD page renders heading and behovsanalyser list or empty state", async ({ page }) => {
    await page.goto("/idd");
    await expect(page.getByRole("heading", { name: /IDD Behovsanalyse/i })).toBeVisible({ timeout: 30_000 });
    // The page shows either a list of behovsanalyser (with count) or the
    // empty state message when no IDD entries exist yet.
    const content = page.locator(
      "text=/behovsanalyser|Ingen behovsanalyser registrert/i"
    ).first();
    await expect(content).toBeVisible({ timeout: 30_000 });
  });

  test("Insurers page renders heading and insurer list or empty state", async ({ page }) => {
    await page.goto("/insurers");
    await expect(page.getByRole("heading", { name: /Forsikringsselskaper/i })).toBeVisible({ timeout: 30_000 });
    // Either insurers are listed or the empty state shows.
    const content = page.locator(
      "text=/selskap|Ingen forsikringsselskaper|Legg til/i"
    ).first();
    await expect(content).toBeVisible({ timeout: 30_000 });
    // The search input is always present.
    await expect(page.getByPlaceholder(/Søk etter selskap/i)).toBeVisible();
  });

  test("SLA page renders Ny avtale wizard", async ({ page }) => {
    await page.goto("/sla");
    await expect(page.getByRole("heading", { name: /Avtaler/i })).toBeVisible({ timeout: 30_000 });
    // The three tabs should be visible.
    await expect(page.getByText("Ny avtale")).toBeVisible();
    await expect(page.getByText("Mine avtaler")).toBeVisible();
    await expect(page.getByText("Meglerinnstillinger")).toBeVisible();
    // The wizard starts on step 1 — "Klientinformasjon" or the org-number lookup.
    // Check that the wizard form is present (it has a "Klient" or "Org.nr" input).
    const wizardContent = page.locator(
      "text=/Klient|Org\\.nr|Steg 1/i"
    ).first();
    await expect(wizardContent).toBeVisible({ timeout: 15_000 });
  });
});
