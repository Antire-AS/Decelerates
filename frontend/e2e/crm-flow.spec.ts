import { test, expect } from "@playwright/test";
import { dismissOnboarding } from "./_helpers";

/**
 * CRM flow — broker navigates to a company profile and interacts with the
 * CRM and Chat tabs.
 *
 * Uses DNB Bank ASA (984851006) as the test fixture — it's always seeded in
 * staging via PDF_SEED_DATA. The profile has 6 tabs: oversikt, okonomi,
 * forsikring, crm, notater, chat.
 */

const DNB_ORGNR = "984851006";

test.describe("CRM and Chat", () => {
  test.beforeEach(async ({ page }) => {
    await dismissOnboarding(page);
  });

  test("DNB profile loads and shows tab bar", async ({ page }) => {
    await page.goto(`/search/${DNB_ORGNR}`);
    await expect(page.getByText(/DNB BANK ASA/i).first()).toBeVisible({ timeout: 30_000 });
    // Tab bar should show all 6 tabs.
    await expect(page.getByText("CRM")).toBeVisible();
    await expect(page.getByText("Chat")).toBeVisible();
  });

  test("CRM tab renders policies section", async ({ page }) => {
    await page.goto(`/search/${DNB_ORGNR}`);
    await expect(page.getByText(/DNB BANK ASA/i).first()).toBeVisible({ timeout: 30_000 });
    // Click the CRM tab.
    await page.getByText("CRM").click();
    // CRM tab renders sub-sections: contacts, policies, claims, activities, etc.
    // At minimum we expect the policies section or a "no data" placeholder.
    const crmContent = page.locator(
      "text=/Avtaler|Poliser|Kontakter|Aktiviteter|Ingen.*data|Ingen.*avtaler/i"
    ).first();
    await expect(crmContent).toBeVisible({ timeout: 30_000 });
  });

  test("Chat tab renders AI chat input", async ({ page }) => {
    await page.goto(`/search/${DNB_ORGNR}`);
    await expect(page.getByText(/DNB BANK ASA/i).first()).toBeVisible({ timeout: 30_000 });
    // Click the Chat tab.
    await page.getByText("Chat").click();
    // The OrgChatSection renders an "AI-chat om DNB BANK ASA" heading and
    // a textarea for user input. We also see suggested questions.
    await expect(page.getByText(/AI-chat/i).first()).toBeVisible({ timeout: 15_000 });
    // The chat textarea should be present.
    const textarea = page.locator("textarea").first();
    await expect(textarea).toBeVisible();
  });

  test("Chat tab has Agent/RAG toggle button", async ({ page }) => {
    await page.goto(`/search/${DNB_ORGNR}`);
    await expect(page.getByText(/DNB BANK ASA/i).first()).toBeVisible({ timeout: 30_000 });
    await page.getByText("Chat").click();
    await expect(page.getByText(/AI-chat/i).first()).toBeVisible({ timeout: 15_000 });
    // The toggle button shows either "RAG" or "Agent".
    const toggleBtn = page.locator("text=/^RAG$|^Agent$/").first();
    await expect(toggleBtn).toBeVisible();
    // Click the toggle — it should switch text.
    const initialText = await toggleBtn.textContent();
    await toggleBtn.click();
    const newText = await toggleBtn.textContent();
    expect(newText).not.toBe(initialText);
  });

  test("Chat tab shows suggested questions", async ({ page }) => {
    await page.goto(`/search/${DNB_ORGNR}`);
    await expect(page.getByText(/DNB BANK ASA/i).first()).toBeVisible({ timeout: 30_000 });
    await page.getByText("Chat").click();
    await expect(page.getByText(/AI-chat/i).first()).toBeVisible({ timeout: 15_000 });
    // The empty chat state shows 3 suggested question buttons.
    await expect(
      page.getByText("Hva er selskapets største risikoer?").first()
    ).toBeVisible({ timeout: 10_000 });
  });
});
