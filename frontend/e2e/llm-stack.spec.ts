import { test, expect, request as pwRequest } from "@playwright/test";

/**
 * LLM-stack tests — exercise the actual Foundry + Vertex AI code paths.
 *
 * These hit the FastAPI backend URL directly (not via the Next.js
 * /bapi/* rewrite) because long-running POSTs like PDF extraction (30–60s)
 * trip the Next.js proxy timeout. The API URL is set in playwright.config.ts
 * via PLAYWRIGHT_API_BASE_URL.
 *
 * 1. GET /ping  → API up
 * 2. GET /companies → DB connection works (this would have caught the
 *    password rotation incident in prod)
 * 3. POST /financials/query → Foundry chat path (NL→SQL via gpt-5.4-mini
 *    on Antire Azure AI Foundry)
 * 4. POST /org/{orgnr}/pdf-history → full Vertex AI path (PDF extraction
 *    via gemini-2.5-flash on Vertex AI europe-west4)
 *
 * Test 4 is the slowest (~30–60s) because it downloads + processes a real
 * 38 MB annual report PDF through Gemini. Per-test timeout in
 * playwright.config.ts is 180s which gives plenty of headroom.
 */

const API_BASE_URL = process.env.PLAYWRIGHT_API_BASE_URL!;
const DNB_ORGNR = "984851006";
const DNB_2023_PDF =
  "https://www.ir.dnb.no/sites/default/files/Annual%20Report%202023.pdf";

test.describe("llm-stack", () => {
  let api: Awaited<ReturnType<typeof pwRequest.newContext>>;

  test.beforeAll(async () => {
    api = await pwRequest.newContext({ baseURL: API_BASE_URL });
  });

  test.afterAll(async () => {
    await api.dispose();
  });

  test("API /ping returns ok", async () => {
    const resp = await api.get("/ping");
    expect(resp.status()).toBe(200);
    expect(await resp.json()).toEqual({ status: "ok" });
  });

  test("/companies returns seeded data (DB connection works)", async () => {
    const resp = await api.get("/companies?limit=5");
    expect(resp.status()).toBe(200);
    const companies = await resp.json();
    expect(Array.isArray(companies)).toBe(true);
    expect(companies.length).toBeGreaterThan(0);
  });

  test("NL→SQL via Foundry returns a SELECT", async () => {
    const resp = await api.post("/financials/query", {
      data: { question: "Top 5 companies by risk_score" },
      timeout: 60_000,
    });
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body.error, `nl-query error: ${body.error}`).toBeFalsy();
    expect(body.sql, "no SQL returned").toBeTruthy();
    expect(body.sql.toUpperCase()).toMatch(/^\s*SELECT/);
  });

  test("PDF extraction via Vertex AI returns valid financials", async () => {
    // Triggers _parse_financials_from_pdf → _try_gemini → Vertex AI
    // gemini-2.5-flash. Expected token cost: ~$0.006 per call.
    const resp = await api.post(`/org/${DNB_ORGNR}/pdf-history`, {
      data: { pdf_url: DNB_2023_PDF, year: 2023, label: "DNB Annual Report 2023" },
      timeout: 150_000,
    });
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body.extracted, "no extracted financials").toBeTruthy();
    // DNB 2023 sanity checks — these are real numbers, not arbitrary thresholds.
    // If extraction degrades to garbage, these will catch it.
    expect(body.extracted.year).toBe(2023);
    expect(body.extracted.revenue).toBeGreaterThan(50_000_000_000);    // > 50 BNOK
    expect(body.extracted.equity).toBeGreaterThan(200_000_000_000);    // > 200 BNOK
    expect(body.extracted.total_assets).toBeGreaterThan(2_000_000_000_000); // > 2 TNOK
    expect(body.extracted.equity_ratio).toBeGreaterThan(0);
    expect(body.extracted.equity_ratio).toBeLessThan(1);
  });
});
