import { expect, test } from "@playwright/test";

import { getBaseUrl, primePageAuth } from "./helpers/auth";

test("recalls export filename preview updates for page-only toggle", async ({
  page,
  request,
}) => {
  await primePageAuth(page, request);
  await page.goto(`${getBaseUrl()}/recalls`, { waitUntil: "domcontentloaded" });

  const csvPreview = page.getByTestId("recalls-export-filename-csv");
  const zipPreview = page.getByTestId("recalls-export-filename-zip");
  await expect(csvPreview).toBeVisible({ timeout: 15_000 });
  await expect(zipPreview).toBeVisible({ timeout: 15_000 });

  const dateStamp = new Date().toISOString().slice(0, 10);
  await expect(csvPreview).toContainText(`recalls-${dateStamp}-filtered.csv`);
  await expect(zipPreview).toContainText(`recall-letters-${dateStamp}-filtered.zip`);

  await page.getByTestId("recalls-export-page-only").check();
  await expect(csvPreview).toContainText(`recalls-${dateStamp}-filtered-page.csv`);
  await expect(zipPreview).toContainText(
    `recall-letters-${dateStamp}-filtered-page.zip`
  );
});
