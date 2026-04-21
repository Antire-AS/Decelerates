import { test, expect } from "@playwright/test";

/**
 * Anbud portal — NO-AUTH route insurers hit via a per-recipient token.
 *
 * Route: /anbud/respond/[token]
 * Backend: GET /bapi/tenders/portal/{token}  +  POST .../upload
 *
 * We don't have a valid token to test against in staging without mutating
 * state, so these tests verify:
 *   (a) the page loads without crashing the frontend,
 *   (b) an invalid token returns the expected "Ugyldig eller utløpt lenke"
 *       error panel rather than a blank page or 5xx.
 *
 * A broker-side e2e that creates a tender + fetches the access token and
 * then visits this URL is a much bigger undertaking — left as a follow-up.
 */

test.describe("Anbud portal", () => {
  test("unknown token renders a clear expired-link message", async ({ page }) => {
    await page.goto("/anbud/respond/definitely-not-a-real-token-xyz");
    // The API returns 404 and the client shows the i18n'd expired-link
    // panel. Any of the page's expected error copy is acceptable.
    await expect(
      page.getByText(/Ugyldig eller utløpt lenke|Kontakt megleren/i).first(),
    ).toBeVisible({ timeout: 15_000 });
  });

  test("invalid token page does NOT render the upload form", async ({ page }) => {
    await page.goto("/anbud/respond/definitely-not-a-real-token-xyz");
    // The form is only shown when the token resolves. Make sure the
    // "Last opp tilbudet" button from the happy path is absent — otherwise
    // a broken error path would let a random visitor attempt an upload
    // against the backend, which would waste rate-limit headroom.
    await expect(page.getByText(/Last opp tilbudet/i)).toBeHidden();
    await expect(page.getByText(/Send tilbud/i)).toBeHidden();
  });

  test("portal layout stays usable on a phone-sized viewport", async ({ page }) => {
    // Insurers often open the link on their phone from the invitation
    // email. Render at an iPhone SE viewport and check the error panel
    // still lays out inside the viewport width.
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto("/anbud/respond/definitely-not-a-real-token-xyz");
    const msg = page.getByText(/Ugyldig eller utløpt lenke|Kontakt megleren/i).first();
    await expect(msg).toBeVisible({ timeout: 15_000 });
    const box = await msg.boundingBox();
    expect(box).not.toBeNull();
    // Allow some margin for padding — if the text overflows past the
    // viewport width, the layout is broken.
    expect(box!.x + box!.width).toBeLessThanOrEqual(375 + 5);
  });
});
