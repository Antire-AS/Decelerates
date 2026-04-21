import { test, expect } from "@playwright/test";

/**
 * Real auth path e2e — only runs when PLAYWRIGHT_AUTH_TEST=1.
 *
 * Existing e2e specs all run against staging with AUTH_DISABLED=1, so
 * the Azure AD / Google OAuth round-trip is never exercised before a
 * broker hits prod's /login. This spec flips that: when the e2e workflow
 * is invoked with `target: auth-test` (see .github/workflows/e2e.yml)
 * it points at an environment whose AUTH_DISABLED env var is unset and
 * runs this file with a dedicated bot account.
 *
 * Required secrets (set in GitHub Actions → Settings → Secrets):
 *   - E2E_AUTH_BOT_EMAIL      — full address of the test account
 *   - E2E_AUTH_BOT_PASSWORD   — its password
 *
 * Provisioning the bot account is a one-time IT task:
 * 1. Create `e2e-bot@<tenant>` in Entra ID with a strong password.
 * 2. Add it to the broker-firm-access group so it gets firm_id=1.
 * 3. Disable MFA for the account (OAuth round-trip via Playwright
 *    cannot clear MFA prompts). Mark the account as non-interactive.
 * 4. Store email + password in the GitHub Actions secrets above.
 *
 * When any of these prerequisites are missing, the specs skip with a
 * clear message instead of failing — so the workflow can be merged and
 * activated later without breaking the default e2e run.
 */

const AUTH_TEST_ENABLED = process.env.PLAYWRIGHT_AUTH_TEST === "1";
const BOT_EMAIL = process.env.E2E_AUTH_BOT_EMAIL;
const BOT_PASSWORD = process.env.E2E_AUTH_BOT_PASSWORD;

test.describe("Real auth round-trip", () => {
  test.skip(
    !AUTH_TEST_ENABLED,
    "PLAYWRIGHT_AUTH_TEST=1 not set — run via the workflow_dispatch 'auth-test' target",
  );
  test.skip(
    AUTH_TEST_ENABLED && (!BOT_EMAIL || !BOT_PASSWORD),
    "E2E_AUTH_BOT_EMAIL / E2E_AUTH_BOT_PASSWORD not configured — see docs/runbooks/auth-e2e-setup.md",
  );

  test("unauthenticated dashboard hit redirects to /login", async ({ page }) => {
    // Clear any NextAuth cookies so we start cold.
    await page.context().clearCookies();
    await page.goto("/dashboard");
    // NextAuth redirects to /api/auth/signin (internally) which then shows
    // /login. Both count as "kicked out" — we accept either URL shape.
    await expect(page).toHaveURL(/\/(login|api\/auth\/signin)/, {
      timeout: 30_000,
    });
  });

  test("Azure AD login completes and lands on /dashboard", async ({ page }) => {
    await page.context().clearCookies();
    await page.goto("/login");

    // Click the Azure AD / Microsoft sign-in button. The visible label is
    // localised, so match loosely.
    await page
      .getByRole("button", { name: /microsoft|azure|logg inn/i })
      .first()
      .click();

    // Microsoft's sign-in screen: email → Next → password → Next.
    // Selectors copied from Entra ID v2 login page (2025-Q4 shape).
    await page.getByLabel(/email|tekst|phone|sign in/i).fill(BOT_EMAIL!);
    await page.getByRole("button", { name: /next|neste/i }).click();

    await page.getByLabel(/password/i).fill(BOT_PASSWORD!);
    await page.getByRole("button", { name: /sign in|logg inn/i }).click();

    // "Stay signed in?" prompt — click No so subsequent test runs don't
    // accumulate persistent sessions on the bot account.
    const stayPrompt = page.getByRole("button", { name: /no|ikke nå/i });
    try {
      await stayPrompt.click({ timeout: 5_000 });
    } catch {
      // Prompt may not appear on every tenant configuration.
    }

    // After the OAuth round-trip NextAuth sets a session cookie and
    // redirects to /dashboard.
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 60_000 });
  });

  test("authenticated request to /bapi/whoami returns the bot's email", async ({
    page,
    request,
  }) => {
    // Run the login spec first via this page, then reuse the cookies for a
    // direct API call. `request` shares the browser context's cookie jar.
    await page.context().clearCookies();
    await page.goto("/login");
    await page
      .getByRole("button", { name: /microsoft|azure|logg inn/i })
      .first()
      .click();
    await page.getByLabel(/email|tekst|phone|sign in/i).fill(BOT_EMAIL!);
    await page.getByRole("button", { name: /next|neste/i }).click();
    await page.getByLabel(/password/i).fill(BOT_PASSWORD!);
    await page.getByRole("button", { name: /sign in|logg inn/i }).click();
    try {
      await page.getByRole("button", { name: /no|ikke nå/i }).click({ timeout: 5_000 });
    } catch {
      /* ignore */
    }
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 60_000 });

    const whoami = await request.get("/bapi/whoami");
    expect(whoami.status()).toBe(200);
    const body = await whoami.json();
    expect(body.email?.toLowerCase()).toBe(BOT_EMAIL!.toLowerCase());
  });
});
