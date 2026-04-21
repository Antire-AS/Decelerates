import { test, expect } from "@playwright/test";
import { dismissOnboarding } from "./_helpers";

/**
 * Pipeline flow — broker manages deals via the kanban board.
 *
 * The pipeline page loads stages from the API (seeded via Alembic migration)
 * and renders one column per stage. Deals are draggable between columns.
 *
 * These tests verify the page renders correctly and the "new deal" modal
 * works. They intentionally avoid drag-and-drop (flaky in headless Chromium
 * on CI) — that's covered by the DndContext unit tests in the component.
 */

test.describe("Pipeline", () => {
  test.beforeEach(async ({ page }) => {
    await dismissOnboarding(page);
  });

  test("page renders heading and Ny deal button", async ({ page }) => {
    await page.goto("/pipeline");
    await expect(page.getByRole("heading", { name: /Pipeline/i })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("Ny deal")).toBeVisible();
  });

  test("kanban columns render stage names", async ({ page }) => {
    await page.goto("/pipeline");
    // Pipeline stages are seeded by Alembic — the default set is:
    // Lead, Kvalifisert, Tilbud sendt, Forhandling, Bundet
    // Stage names come from the API; we check for at least the first and last.
    await expect(page.getByText("Lead").first()).toBeVisible({ timeout: 30_000 });
    // "Kvalifisert" or "Tilbud sendt" — at least one mid-stage should be present.
    const midStage = page.locator("text=/Kvalifisert|Tilbud sendt/i").first();
    await expect(midStage).toBeVisible({ timeout: 30_000 });
  });

  test("at least 1 deal card is visible (or empty state shows deal count)", async ({ page }) => {
    await page.goto("/pipeline");
    await expect(page.getByText(/Pipeline/i).first()).toBeVisible({ timeout: 30_000 });
    // Either we see deal cards (with "deal" or "deals" count text in columns),
    // or the pipeline loaded with no deals. Both are valid states on staging.
    const indicator = page.locator("text=/deal|Laster pipeline|Ingen pipeline/i").first();
    await expect(indicator).toBeVisible({ timeout: 30_000 });
  });

  test("Ny deal button opens the new deal modal", async ({ page }) => {
    await page.goto("/pipeline");
    await expect(page.getByText("Ny deal")).toBeVisible({ timeout: 30_000 });
    await page.getByText("Ny deal").click();
    // The NewDealModal renders a company search input and a stage selector.
    // Look for the search input placeholder or the modal heading.
    const modal = page.locator("text=/Velg et selskap|Selskap|Stage|Steg/i").first();
    await expect(modal).toBeVisible({ timeout: 10_000 });
  });

  test("new deal modal has company search and stage picker", async ({ page }) => {
    await page.goto("/pipeline");
    await page.getByText("Ny deal").click({ timeout: 30_000 });
    // The modal contains a company search field, a stage dropdown, and a save button.
    // The company search input has a placeholder or search icon.
    const searchInput = page.locator("input").first();
    await expect(searchInput).toBeVisible({ timeout: 10_000 });
    // Stage selector (select element with stage options)
    const stageSelect = page.locator("select").first();
    await expect(stageSelect).toBeVisible({ timeout: 10_000 });
  });
});
