import { test, expect } from "@playwright/test";

/**
 * Search flow — broker types in a company name (or org number), picks a
 * result, lands on the company profile.
 *
 * Uses DNB Bank ASA (orgnr 984851006) as the canonical test fixture: it's
 * always seeded in both staging and prod via PDF_SEED_DATA in
 * api/constants.py, so the search will always return at least one hit.
 */

const DNB_ORGNR = "984851006";

test("search-flow: search page renders heading and input", async ({ page }) => {
  await page.goto("/search");
  // The search page renders an h1 "Selskapsøk" and a placeholder hinting
  // at the org-number example "F.eks. DNB BANK ASA eller 984851006".
  await expect(page.getByRole("heading", { name: /selskapsøk/i })).toBeVisible();
  await expect(page.getByPlaceholder(/F\.eks.*DNB|F\.eks.*\d{9}/i).first()).toBeVisible();
});

test("search-flow: open DNB profile by orgnr direct URL", async ({ page }) => {
  await page.goto(`/search/${DNB_ORGNR}`);
  // Profile header must show the company name.
  await expect(page.getByText(/DNB BANK ASA/i).first()).toBeVisible({ timeout: 30_000 });
  // Org number is shown somewhere on the profile.
  await expect(page.getByText(DNB_ORGNR).first()).toBeVisible();
});

test("search-flow: profile shows financial metrics", async ({ page }) => {
  await page.goto(`/search/${DNB_ORGNR}`);
  // Wait for the profile to fully load — financial data should be visible
  // (DNB has 6 years of cached company_history rows seeded).
  await expect(page.getByText(/DNB BANK ASA/i).first()).toBeVisible({ timeout: 30_000 });
  // The risk score / equity ratio / revenue / risk badge — at least one
  // financial metric should appear. The label varies by tab so we check for
  // a generic "MNOK" or "%" pattern that financial widgets always render.
  const financialIndicator = page
    .locator("text=/MNOK|kr [0-9]|[0-9]+\\.[0-9]+\\s*%|risikoskår|risk score/i")
    .first();
  await expect(financialIndicator).toBeVisible({ timeout: 30_000 });
});
