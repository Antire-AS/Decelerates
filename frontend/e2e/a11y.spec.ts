import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/**
 * WCAG 2.1 AA gate — runs axe-core against the 6 highest-traffic
 * broker surfaces. Any new "serious" or "critical" violation fails the
 * test. Tier 1 of the 2026-04-17 usability initiative locked in the
 * baseline; this spec prevents regressions.
 *
 * Excluded rules (rationale per rule):
 *   - color-contrast: brand palette has been manually verified above
 *     AAA on text. Re-enable when Tier 2 introduces shadcn primitives
 *     and we can audit each component once.
 *
 * The seeded DNB orgnr (984851006) is always available in staging and
 * matches the search-flow.spec.ts fixture.
 */

const DNB_ORGNR = "984851006";

const SURFACES: Array<{ path: string; label: string }> = [
  { path: "/dashboard", label: "dashboard" },
  { path: "/search", label: "search" },
  { path: `/search/${DNB_ORGNR}`, label: "search/[orgnr]" },
  { path: "/portfolio", label: "portfolio" },
  { path: "/renewals", label: "renewals" },
  { path: "/knowledge", label: "knowledge" },
];

for (const { path, label } of SURFACES) {
  test(`a11y: ${label} has no serious or critical axe violations`, async ({ page }) => {
    await page.goto(path);
    // Give SWR fetches and lazy-loaded tab content a moment to render.
    await page.waitForLoadState("networkidle", { timeout: 30_000 });
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .disableRules(["color-contrast"])
      .analyze();

    const blocking = results.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical",
    );

    if (blocking.length > 0) {
      // Pretty-print the violations so CI logs are actionable.
      console.error(
        `Axe violations on ${label}:\n` +
          blocking
            .map(
              (v) =>
                `  [${v.impact}] ${v.id}: ${v.help}\n` +
                v.nodes.map((n) => `    - ${n.target.join(", ")}`).join("\n"),
            )
            .join("\n"),
      );
    }
    expect(blocking, `Axe found ${blocking.length} serious/critical violations on ${label}`).toEqual([]);
  });
}
