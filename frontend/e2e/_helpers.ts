import type { Page } from "@playwright/test";

/**
 * Dismiss the first-visit onboarding guide overlay before the page loads.
 *
 * The OnboardingTour in `frontend/src/components/layout/OnboardingTour.tsx`
 * reads `localStorage["ba_onboarding_seen"]` and opens a 6-step modal when
 * it's missing. Playwright fresh contexts always see an empty localStorage,
 * so the modal covers the page content and blocks tab clicks.
 *
 * Call this BEFORE `page.goto(...)` in new spec files so the script runs
 * on every navigation in the context. Mirrors the real user's returning-
 * visit state without mutating any backend data.
 */
export async function dismissOnboarding(page: Page): Promise<void> {
  await page.addInitScript(() => {
    try {
      localStorage.setItem("ba_onboarding_seen", "1");
    } catch {
      /* localStorage unavailable — no-op */
    }
  });
}
