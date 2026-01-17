import { expect, test } from "@playwright/test";

import { getBaseUrl, primePageAuth } from "./helpers/auth";

function extractFilename(text: string | null) {
  if (!text) return "";
  const [, filename] = text.split(":");
  return (filename || "").trim();
}

function expectSafeFilename(value: string) {
  expect(value).toBeTruthy();
  expect(value).not.toMatch(/[\\/:*?"<>|]/);
  expect(value.length).toBeLessThanOrEqual(120);
}

test("recalls export filename preview matches download and sanitizes", async ({
  page,
  request,
}) => {
  await primePageAuth(page, request);
  await page.goto(`${getBaseUrl()}/recalls`, { waitUntil: "domcontentloaded" });

  const csvPreview = page.getByTestId("recalls-export-filename-csv");
  const zipPreview = page.getByTestId("recalls-export-filename-zip");
  const exportSummary = page.getByTestId("recalls-export-summary");
  const exportCsvButton = page.getByTestId("recalls-export-csv");
  const exportZipButton = page.getByTestId("recalls-export-zip");
  await expect(csvPreview).toBeVisible({ timeout: 15_000 });
  await expect(zipPreview).toBeVisible({ timeout: 15_000 });
  await expect(exportSummary).toBeVisible({ timeout: 15_000 });
  await expect(exportCsvButton).toBeDisabled();
  await expect(exportZipButton).toBeDisabled();
  await expect(exportCsvButton).toBeEnabled({ timeout: 15_000 });
  await expect(exportZipButton).toBeEnabled({ timeout: 15_000 });

  for (const label of ["Upcoming", "Completed", "Cancelled"]) {
    const checkbox = page.getByLabel(label);
    if (!(await checkbox.isChecked())) {
      await checkbox.check();
    }
  }

  const dateStamp = new Date().toISOString().slice(0, 10);
  await expect(csvPreview).toContainText(`recalls-${dateStamp}-filtered.csv`);
  await expect(zipPreview).toContainText(`recall-letters-${dateStamp}-filtered.zip`);

  const csvFilename = extractFilename(await csvPreview.textContent());
  const zipFilename = extractFilename(await zipPreview.textContent());
  expectSafeFilename(csvFilename);
  expectSafeFilename(zipFilename);

  const summaryText = (await exportSummary.textContent()) || "";
  if (summaryText.includes("0 recalls")) {
    await page.getByTestId("recalls-export-page-only").check();
    await expect(csvPreview).toContainText(
      `recalls-${dateStamp}-filtered-page.csv`
    );
    await expect(zipPreview).toContainText(
      `recall-letters-${dateStamp}-filtered-page.zip`
    );
    return;
  }

  const [csvDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.getByTestId("recalls-export-csv").click(),
  ]);
  expect(csvDownload.suggestedFilename()).toBe(csvFilename);

  const [zipDownload] = await Promise.all([
    page.waitForEvent("download", { timeout: 60_000 }),
    page.getByTestId("recalls-export-zip").click(),
  ]);
  expect(zipDownload.suggestedFilename()).toBe(zipFilename);

  await page.getByTestId("recalls-export-page-only").check();
  await expect(csvPreview).toContainText(`recalls-${dateStamp}-filtered-page.csv`);
  await expect(zipPreview).toContainText(`recall-letters-${dateStamp}-filtered-page.zip`);
});
