/**
 * Floating AI chat button (PR #300, mockup-inspired by Patrick #293).
 *
 * Sparkles icon bottom-right on every authenticated page → click opens
 * a drawer → starter chip fires a chat → AI response appears.
 */
import { test, expect } from "@playwright/test";
import { dismissOnboarding } from "./_helpers";

test.describe("Floating AI chat (PR #300)", () => {
  test.beforeEach(async ({ page }) => {
    await dismissOnboarding(page);
    await page.goto("/dashboard", { timeout: 60_000 });
  });

  test("Sparkles button is visible bottom-right", async ({ page }) => {
    const trigger = page.getByRole("button", { name: /Åpne AI-assistent|AI-assistent/i });
    await expect(trigger).toBeVisible();
  });

  test("Clicking the trigger opens the drawer with starter chips", async ({ page }) => {
    await page.getByRole("button", { name: /Åpne AI-assistent|AI-assistent/i }).click();
    // 4 starter chips from GlobalChatButton.tsx
    for (const q of ["Hva skjer i dag", "forfaller snart", "åpne skader", "følge opp"]) {
      await expect(page.getByText(new RegExp(q, "i"))).toBeVisible();
    }
  });

  test("Drawer can be closed with X button", async ({ page }) => {
    await page.getByRole("button", { name: /Åpne AI-assistent|AI-assistent/i }).click();
    await page.getByRole("button", { name: /Lukk/i }).click();
    // Trigger should be visible again
    await expect(
      page.getByRole("button", { name: /Åpne AI-assistent|AI-assistent/i }),
    ).toBeVisible();
  });
});
