/**
 * Admin metrics + service-status panel (PR #297, mockup 11.03.34).
 *
 * /admin renders 4 metric cards on top + Eksterne tjenester panel
 * (with service health pills) + AuditLogSection.
 */
import { test, expect } from "@playwright/test";
import { dismissOnboarding } from "./_helpers";

test.describe("Admin metrics panel (PR #297)", () => {
  test.beforeEach(async ({ page }) => {
    await dismissOnboarding(page);
    await page.goto("/admin", { timeout: 60_000 });
  });

  test("4 metric cards visible at top", async ({ page }) => {
    await expect(page.getByRole("heading", { name: /Administrasjon/i })).toBeVisible();
    // Card labels (uppercase tracking-wide)
    for (const label of [
      /Aktive brukere/i,
      /API-kall siste 24t/i,
      /AI-tokens i dag/i,
      /Lagring/i,
    ]) {
      await expect(page.getByText(label).first()).toBeVisible();
    }
  });

  test("Eksterne tjenester panel lists 7 known services", async ({ page }) => {
    const heading = page.getByRole("heading", { name: /Eksterne tjenester/i });
    await expect(heading).toBeVisible();
    // 7 services from api/routers/admin_metrics.py:_SERVICES
    const services = [
      "BRREG Enhetsregisteret",
      "BRREG Regnskapsregisteret",
      "Azure AI Foundry",
      "GCP Vertex AI",
      "OpenSanctions PEP",
      "Kartverket Geonorge",
      "Løsøreregisteret",
    ];
    const card = heading.locator("..");
    for (const name of services) {
      await expect(card.getByText(name).first()).toBeVisible({ timeout: 30_000 });
    }
  });
});
