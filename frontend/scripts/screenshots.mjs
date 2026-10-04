/**
 * Capture README screenshots from the running app using a real public DRHP.
 *
 *   node scripts/screenshots.mjs <path-to-drhp.pdf> "<Company name>" [outDir]
 *
 * Needs the backend on :8000 and the frontend on :3000 (see README). Uses the
 * Chromium that Playwright finds (PLAYWRIGHT_BROWSERS_PATH) — nothing is downloaded.
 */
import { chromium } from "@playwright/test";
import path from "node:path";

const [pdf, company, outDir = "../docs/images"] = process.argv.slice(2);
if (!pdf || !company) {
  console.error('usage: node scripts/screenshots.mjs <drhp.pdf> "<Company name>" [outDir]');
  process.exit(2);
}
const BASE = process.env.APP_URL ?? "http://localhost:3000";
const out = (name) => path.resolve(outDir, `${name}.png`);

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1360, height: 820 }, colorScheme: "light" });
page.setDefaultTimeout(30_000);
const snap = async (name, opts = {}) => {
  await page.waitForTimeout(400);
  await page.screenshot({ path: out(name), ...opts });
  console.log("saved", name);
};

// 1. Create the case
await page.goto(`${BASE}/cases/new`);
await page.getByLabel(/company name/i).fill(company);
await page.locator('input[name="route"][value="mainboard_reg6_1"]').check();
await page.getByRole("button", { name: /create case/i }).click();
await page.waitForURL(/\/cases\/[0-9a-f-]+/);
const caseUrl = page.url().split("?")[0];

// 2. Upload the DRHP and wait for extraction
await page.locator('input[type="file"]').setInputFiles(pdf);
await page.getByRole("cell", { name: /awaiting review|completed/i }).first().waitFor({ timeout: 600_000 });

// 3. Document view: extracted fields with page, printed value and unit
await page.locator('a[href^="/documents/"]').first().click();
await page.getByRole("heading", { name: /field outcomes/i }).waitFor();
await page.getByLabel(/filter by status/i).selectOption("extracted_high_confidence");
await snap("document-fields");

// 4. Page preview of the eligibility table
await page.locator("td.num button").first().click();
await page.getByRole("dialog").waitFor();
await page.getByRole("dialog").getByRole("img").waitFor();
await snap("page-preview");
await page.keyboard.press("Escape");

// 5. Review queue for the case
await page.goto(`${caseUrl}?tab=review`);
await page.waitForTimeout(1500);
await snap("review");

// 6. Run screening → report
await page.goto(`${caseUrl}?tab=overview`);
await page.getByRole("button", { name: /run screening/i }).first().click();
await page.waitForURL(/\/reports\//, { timeout: 60_000 });
await page.locator("#rule-NTA_3CR > summary").waitFor();
await snap("report");
await page.locator("#rule-NTA_3CR > summary").click();
await page.locator("#rule-NTA_3CR").scrollIntoViewIfNeeded();
await snap("rule-detail");

// 7. Gap planner
await page.getByRole("tab", { name: /gap planner/i }).click();
await snap("gaps");

// 8. Rule explorer
await page.goto(`${BASE}/rules`);
await page.getByRole("heading", { name: "Rule explorer" }).waitFor();
await snap("rules");

await browser.close();
