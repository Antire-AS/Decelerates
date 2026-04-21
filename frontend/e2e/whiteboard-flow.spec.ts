import { test, expect } from "@playwright/test";
import { dismissOnboarding } from "./_helpers";

/**
 * Fokus whiteboard — per-company scratchpad for facts the broker wants in
 * one place (from Oversikt / Økonomi / Forsikring), plus free-text notes
 * and an optional "generate AI summary" trigger.
 *
 * Uses DNB Bank ASA (984851006) — always seeded in staging via
 * PDF_SEED_DATA in api/constants.py.
 *
 * Waits on /org/{orgnr} returning rather than DOM text, so a slow
 * profile hydrate doesn't race the tab-click assertion on cold starts.
 */

const DNB_ORGNR = "984851006";

async function gotoProfile(page: import("@playwright/test").Page) {
  const orgResponse = page.waitForResponse(
    (resp) => resp.url().includes(`/org/${DNB_ORGNR}`) && resp.status() === 200,
    { timeout: 60_000 },
  );
  await page.goto(`/search/${DNB_ORGNR}`);
  await orgResponse;
}

test.describe("Fokus whiteboard", () => {
  test.beforeEach(async ({ page }) => {
    await dismissOnboarding(page);
  });

  test("Fokus tab is reachable from the company profile", async ({ page }) => {
    await gotoProfile(page);
    const fokusTab = page.getByText("Fokus").first();
    await expect(fokusTab).toBeVisible({ timeout: 30_000 });
    await fokusTab.click();
    // After clicking, the tab content should show "Fakta om <company>" —
    // the canonical heading from WhiteboardTab.tsx.
    await expect(page.getByText(/Fakta om/i).first()).toBeVisible({
      timeout: 15_000,
    });
  });

  test("whiteboard renders without the spinner after load", async ({ page }) => {
    await gotoProfile(page);
    await page.getByText("Fokus").first().click();
    // The "Laster fokus-whiteboard…" spinner should disappear once
    // GET /whiteboard/{orgnr} returns. Regression signal if it sticks.
    await expect(page.getByText(/Laster fokus-whiteboard…/i)).toBeHidden({
      timeout: 15_000,
    });
  });

  test("whiteboard shows empty-state prompt or existing items", async ({ page }) => {
    await gotoProfile(page);
    await page.getByText("Fokus").first().click();
    // Either items exist (the remove "Fjern" title-tooltip) or we see the
    // empty-state hint. Both are valid landings.
    const empty = page.getByText(/Dra eller skriv inn fakta/i).first();
    const filled = page.locator('[title="Fjern"]').first();
    await expect(empty.or(filled)).toBeVisible({ timeout: 15_000 });
  });
});
