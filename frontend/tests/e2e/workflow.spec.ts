import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

const SHOTS = process.env.E2E_SCREENSHOT_DIR;
const shot = async (page: import("@playwright/test").Page, name: string) => {
  if (SHOTS) await page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage: true });
};

/** Generate a synthetic DRHP PDF with the backend's fixture factory (synthetic, not real-world data). */
function syntheticDrhp(): string {
  const dir = mkdtempSync(path.join(tmpdir(), "e2e-"));
  const out = path.join(dir, "acme-drhp.pdf");
  const backend = path.resolve(__dirname, "../../../backend");
  execFileSync(path.resolve(backend, "../.venv/bin/python"), ["-c", `import sys; sys.path.insert(0, '.'); from tests.fixtures.pdf_factory import standard_drhp; open(${JSON.stringify(out)}, 'wb').write(standard_drhp())`], { cwd: backend });
  return out;
}

test("full screening workflow: case → upload → review → screen → report", async ({ page }) => {
  const company = `E2E Acme ${Date.now()}`;
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await shot(page, "01-dashboard");

  // New case with validation
  await page.getByRole("link", { name: /new screening case/i }).first().click();
  await page.getByRole("button", { name: /create case/i }).click();
  await expect(page.getByText("Company name is required.")).toBeVisible();
  await page.getByLabel(/company name/i).fill(company);
  await shot(page, "02-new-case");
  await page.getByRole("button", { name: /create case/i }).click();
  await expect(page).toHaveURL(/\/cases\/[0-9a-f-]+\?tab=documents/);

  // Upload a non-PDF is rejected client-side
  const input = page.locator('input[type="file"]');
  await input.setInputFiles({ name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("hello") });
  await expect(page.getByText("Only PDF files are supported.")).toBeVisible();

  // Upload synthetic DRHP; wait for extraction
  await input.setInputFiles(syntheticDrhp());
  await expect(page.getByText(/extraction started/i)).toBeVisible();
  await expect(page.getByRole("cell", { name: /awaiting review|completed/i }).first()).toBeVisible({ timeout: 60_000 });
  await shot(page, "03-documents");

  // Evidence & data shows extracted NTA with provenance
  await page.getByRole("tab", { name: /evidence & data/i }).click();
  await expect(page.getByText("₹123.4567 Cr").first()).toBeVisible();
  await shot(page, "04-facts");

  // Review workspace: confirm every open item
  await page.getByRole("tab", { name: /^review/i }).click();
  const openList = page.getByRole("region", { name: "Open review items" });
  const cards = openList.locator("article.card");
  await expect(cards.first()).toBeVisible();
  const n = await cards.count();
  await shot(page, "05-review");
  for (let i = 0; i < n; i++) {
    const card = cards.first();
    await card.getByLabel(/reason/i).fill("Checked against the declaration on page 3.");
    await card.getByRole("button", { name: /record decision/i }).click();
    await expect(cards).toHaveCount(n - i - 1, { timeout: 15_000 });
  }
  await expect(page.getByText(/nothing awaiting review/i)).toBeVisible();

  // Run screening -> report
  await page.getByRole("button", { name: /run screening/i }).first().click();
  await expect(page).toHaveURL(/\/reports\//, { timeout: 30_000 });
  await expect(page.getByText(/insufficient evidence/i).first()).toBeVisible();
  await expect(page.getByText(/decision support only/i).first()).toBeVisible();
  await shot(page, "06-report");

  // Expand NTA rule: calculation + evidence with page link
  await page.locator("#rule-NTA_3CR > summary").click();
  await expect(page.locator("#rule-NTA_3CR").getByText(/12,345.67/).first()).toBeVisible();
  await page.locator("#rule-NTA_3CR").getByRole("button", { name: "View" }).first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("img", { name: /page 2/i })).toBeVisible();
  await shot(page, "07-page-preview");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toBeHidden();

  // Reopening the same page reuses the cached image; it must still render.
  await page.locator("#rule-NTA_3CR").getByRole("button", { name: "View" }).first().click();
  const reopened = page.getByRole("img", { name: /page 2/i });
  await expect(reopened).toBeVisible();
  await expect.poll(() => reopened.evaluate((el) => (el as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toBeHidden();

  // Evidence register, gap planner, limitations, sign-off validation
  await page.getByRole("tab", { name: /evidence register/i }).click();
  await expect(page.getByText(/calculated values are never/i)).toBeVisible();
  await page.getByRole("tab", { name: /gap planner/i }).click();
  await expect(page.getByText(/not a regulatory failure/i).first()).toBeVisible();
  await shot(page, "08-gaps");
  await page.getByRole("tab", { name: /human sign-off/i }).click();
  await page.getByRole("button", { name: /record decision/i }).click();
  await expect(page.getByText("Reviewer name is required.")).toBeVisible();
});

test("rule explorer, settings and empty/error states", async ({ page }) => {
  await page.goto("/rules");
  await expect(page.getByRole("heading", { name: "Rule explorer" })).toBeVisible();
  await expect(page.getByText(/superseded/i).first()).toBeVisible();
  const scrr = page.locator("details.rule", { hasText: "Minimum public offer (SCRR Rule 19(2)(b), 2026 tiers)" });
  await scrr.locator("summary").click();
  await expect(scrr.getByText(/secondary sources only/i).first()).toBeVisible();
  await expect(scrr.getByText(/G.S.R. 184\(E\)/).first()).toBeVisible();
  await shot(page, "09-rules");

  await page.goto("/settings");
  await expect(page.getByText(/none — all processing is local/i)).toBeVisible();
  await shot(page, "10-settings");

  await page.goto("/cases?x=1");
  await page.getByLabel(/search by company name/i).fill("zzz-no-such-company");
  await expect(page.getByText(/no matching cases/i)).toBeVisible();

  await page.goto("/reports/00000000-0000-0000-0000-000000000000");
  await expect(page.getByText(/not found/i).first()).toBeVisible();
  await page.goto("/definitely-missing");
  await expect(page.getByText(/page not found/i)).toBeVisible();
});

test("keyboard: skip link and tab focus", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.getByText("Skip to content")).toBeFocused();
});
