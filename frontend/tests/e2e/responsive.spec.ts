import { expect, test } from "@playwright/test";
import path from "node:path";

test("narrow viewport: navigation drawer and no horizontal page scroll", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await page.getByRole("button", { name: /toggle navigation/i }).click();
  await page.getByRole("link", { name: "Rule explorer" }).click();
  await expect(page.getByRole("heading", { name: "Rule explorer" })).toBeVisible();
  if (process.env.E2E_SCREENSHOT_DIR) await page.screenshot({ path: path.join(process.env.E2E_SCREENSHOT_DIR, "11-mobile-rules.png"), fullPage: true });
});
