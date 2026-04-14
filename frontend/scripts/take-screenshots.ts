/**
 * Take screenshots of the app pages for use in Remotion demo videos.
 * Run: npx tsx scripts/take-screenshots.ts
 */
import { chromium } from "playwright";

const BASE = "http://localhost:3000";
const OUT = "public/demo";

const PAGES = [
  { name: "dashboard", path: "/dashboard" },
  { name: "search", path: "/search" },
  { name: "portfolio", path: "/portfolio" },
  { name: "pipeline", path: "/pipeline" },
  { name: "renewals", path: "/renewals" },
  { name: "idd", path: "/idd" },
  { name: "knowledge", path: "/knowledge" },
  { name: "sla", path: "/sla" },
  { name: "admin", path: "/admin" },
  { name: "search-dnb", path: "/search/984851006" },
];

async function main() {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });

  const page = await ctx.newPage();

  // First visit to set localStorage (dismiss onboarding)
  await page.goto(`${BASE}/dashboard`, { waitUntil: "domcontentloaded", timeout: 15000 });
  await page.evaluate(() => {
    localStorage.setItem("ba_onboarding_seen", "1");
  });

  for (const { name, path } of PAGES) {
    console.log(`📸 ${name} → ${path}`);
    await page.goto(`${BASE}${path}`, { waitUntil: "domcontentloaded", timeout: 15000 });
    // Wait for React to hydrate — sidebar nav is the signal
    await page.waitForSelector("nav a", { timeout: 8000 }).catch(() => {});
    // Let animations settle and API calls fail gracefully
    await page.waitForTimeout(3000);
    await page.screenshot({ path: `${OUT}/${name}.png`, type: "png" });
  }

  await browser.close();
  console.log(`\n✅ Screenshots saved to ${OUT}/`);
}

main().catch(console.error);
