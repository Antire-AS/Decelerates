import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config for Decelerates e2e tests.
 *
 * Auth is currently disabled in the frontend (`/login` redirects straight to
 * `/dashboard`) and the backend uses `AUTH_DISABLED=true` in dev/staging, so
 * tests can hit any page directly without going through Azure AD.
 *
 * Targets staging by default. Override with PLAYWRIGHT_BASE_URL env var to
 * point at a different environment, e.g.:
 *   PLAYWRIGHT_BASE_URL=http://localhost:3000 npx playwright test
 *   PLAYWRIGHT_BASE_URL=https://ca-frontend.whitepebble-... npx playwright test
 */
const STAGING_FRONTEND_URL =
  "https://ca-frontend-staging.whitepebble-3ac25616.norwayeast.azurecontainerapps.io";
const STAGING_API_URL =
  "https://ca-api-staging.whitepebble-3ac25616.norwayeast.azurecontainerapps.io";

// Backend tests in e2e/llm-stack.spec.ts hit the FastAPI URL directly
// (not via the Next.js /bapi/* rewrite), because long-running POSTs like
// PDF extraction (30–60s) trip the Next.js proxy timeout. Override with
// PLAYWRIGHT_API_BASE_URL when running against another env.
const API_BASE_URL = process.env.PLAYWRIGHT_API_BASE_URL || STAGING_API_URL;
process.env.PLAYWRIGHT_API_BASE_URL = API_BASE_URL;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || STAGING_FRONTEND_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    // Generous timeouts — staging cold-start can take 15s, and PDF
    // extraction calls hit Vertex AI which can take 10–30s on large reports.
    actionTimeout: 30_000,
    navigationTimeout: 60_000,
  },
  // Per-test timeout. PDF extraction tests need ~3 min to wait for the
  // backend Vertex AI call to complete on cold-cache rows.
  timeout: 180_000,
  expect: {
    timeout: 30_000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
