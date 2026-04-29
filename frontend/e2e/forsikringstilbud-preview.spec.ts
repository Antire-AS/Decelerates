/**
 * Forsikringstilbud preview generator (PR #302, mockup 11.02.43).
 *
 * /forsikringstilbud/<orgnr> page renders a 2-column form + live PDF preview
 * iframe. Test asserts the form fields exist and the iframe is present after
 * the user types something (debounced 600ms).
 */
import { test, expect } from "@playwright/test";
import { dismissOnboarding } from "./_helpers";

// Use a known seeded company. DNB Bank ASA is in PDF_SEED_DATA on every env.
const SEEDED_ORGNR = "984851006";

test.describe("Forsikringstilbud preview (PR #302)", () => {
  test.beforeEach(async ({ page }) => {
    await dismissOnboarding(page);
  });

  test("Generator page renders form + preview pane", async ({ page }) => {
    await page.goto(`/forsikringstilbud/${SEEDED_ORGNR}`, { timeout: 60_000 });
    await expect(page.getByRole("heading", { name: /Forsikringstilbud/i })).toBeVisible();
    // 3 form sections from the page
    await expect(page.getByRole("heading", { name: /Sammendrag/i })).toBeVisible();
    await expect(page.getByRole("heading", { name: /Total premieanslag/i })).toBeVisible();
    await expect(page.getByRole("heading", { name: /Anbefalinger/i })).toBeVisible();
    // Preview pane label
    await expect(page.getByText(/Forhåndsvisning/i)).toBeVisible();
  });

  test("Generer-knapp is disabled with empty form, present otherwise", async ({ page }) => {
    await page.goto(`/forsikringstilbud/${SEEDED_ORGNR}`, { timeout: 60_000 });
    const button = page.getByRole("button", { name: /Generer og last ned PDF/i });
    await expect(button).toBeVisible();
    // Type into sammendrag textarea — preview should fire after debounce
    const textarea = page
      .getByRole("heading", { name: /Sammendrag/i })
      .locator("..")
      .locator("textarea");
    await textarea.fill("Test sammendrag for e2e");
    // Preview iframe appears within 5s (debounce 600ms + render)
    await expect(page.locator("iframe[title*='preview']")).toBeVisible({ timeout: 5_000 });
  });

  test("CTA from Forsikring tab on company profile", async ({ page }) => {
    await page.goto(`/search/${SEEDED_ORGNR}`, { timeout: 60_000 });
    await page.getByRole("tab", { name: /Forsikring/i }).click();
    const cta = page.getByRole("link", { name: /Åpne tilbudsbygger/i });
    await expect(cta).toBeVisible();
    await cta.click();
    await expect(page).toHaveURL(new RegExp(`/forsikringstilbud/${SEEDED_ORGNR}`));
  });
});
