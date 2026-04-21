import { test, expect } from "@playwright/test";
import { dismissOnboarding } from "./_helpers";

/**
 * Chat memory — the Chat tab on /search/[orgnr] rehydrates prior
 * broker-scoped conversation for the same company across page loads via
 * `getChatHistory(orgnr)` on mount (see OrgChatSection.tsx).
 *
 * Follows the crm-flow.spec.ts pattern for tab interaction. We verify:
 *   (a) the chat textarea is rendered after clicking Chat,
 *   (b) the history endpoint is actually hit (network trace),
 *   (c) the textarea accepts typing (composer is wired up).
 *
 * We intentionally do NOT assert on the contents of any rehydrated
 * messages — history on staging is whatever prior test runs wrote.
 * Asserting on the FETCH firing is enough to catch regressions.
 */

const DNB_ORGNR = "984851006";

test.describe("Chat memory", () => {
  test.beforeEach(async ({ page }) => {
    await dismissOnboarding(page);
  });

  test("Chat tab renders a textarea composer", async ({ page }) => {
    await page.goto(`/search/${DNB_ORGNR}`);
    await expect(page.getByText(/DNB BANK ASA/i).first()).toBeVisible({
      timeout: 30_000,
    });
    await page.getByText("Chat").first().click();
    await expect(page.locator("textarea").first()).toBeVisible({
      timeout: 15_000,
    });
  });

  test("opening the Chat tab fires a /chat/history fetch (hydrate-on-mount)", async ({
    page,
  }) => {
    const historyPromise = page.waitForRequest(
      (req) =>
        req.url().includes("/chat/history") &&
        req.url().includes(DNB_ORGNR) &&
        req.method() === "GET",
      { timeout: 30_000 },
    );
    await page.goto(`/search/${DNB_ORGNR}`);
    await expect(page.getByText(/DNB BANK ASA/i).first()).toBeVisible({
      timeout: 30_000,
    });
    await page.getByText("Chat").first().click();
    // If the fetch doesn't fire, the hydrate-on-mount path regressed —
    // the test times out here instead of silently reporting green.
    const request = await historyPromise;
    expect(request.url()).toContain("/chat/history");
  });

  test("Chat input accepts typing", async ({ page }) => {
    await page.goto(`/search/${DNB_ORGNR}`);
    await expect(page.getByText(/DNB BANK ASA/i).first()).toBeVisible({
      timeout: 30_000,
    });
    await page.getByText("Chat").first().click();
    const composer = page.locator("textarea").first();
    await expect(composer).toBeVisible({ timeout: 15_000 });
    await composer.fill("Hei");
    await expect(composer).toHaveValue("Hei");
  });
});
