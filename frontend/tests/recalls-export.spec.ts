import { expect, test } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

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

test("recalls export CSV shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Recall",
    last_name: `Export Hardening ${Date.now()}`,
  });
  const token = await ensureAuthReady(request);
  const dueDate = new Date().toISOString().slice(0, 10);
  const recallResponse = await request.post(`${baseUrl}/api/patients/${patientId}/recalls`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      kind: "exam",
      due_date: dueDate,
      notes: "Recall export hardening proof",
    },
  });
  expect(recallResponse.ok()).toBeTruthy();

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/recalls`, { waitUntil: "domcontentloaded" });

  const exportButton = page.getByTestId("recalls-export-csv");
  await expect(exportButton).toBeEnabled({ timeout: 15_000 });

  let seenRequest!: () => void;
  const seenRequestPromise = new Promise<void>((resolve) => {
    seenRequest = resolve;
  });
  let releaseResponse!: () => void;
  const releaseResponsePromise = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });
  let requestCount = 0;
  const routePattern = /\/api\/recalls\/export\.csv\?/;

  await page.route(routePattern, async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    requestCount += 1;
    if (requestCount === 1) {
      seenRequest();
    }
    await releaseResponsePromise;
    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "text/csv",
        "Content-Disposition": 'attachment; filename="recalls-export-proof.csv"',
      },
      body: "patient_id,due_date,status\n1,2026-03-22,due\n",
    });
  });

  const downloadPromise = page.waitForEvent("download");
  const clickState = await exportButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Recall export CSV button not found");
    }
    const beforeDisabled = button.disabled;
    button.click();
    const afterFirstDisabled = button.disabled;
    button.click();
    return { beforeDisabled, afterFirstDisabled, afterSecondDisabled: button.disabled };
  });
  await seenRequestPromise;

  expect(clickState.beforeDisabled).toBe(false);
  expect(clickState.afterFirstDisabled).toBe(true);
  expect(clickState.afterSecondDisabled).toBe(true);
  await expect(exportButton).toBeDisabled();
  await expect(exportButton).toHaveText("Exporting...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseResponse();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("recalls-export-proof.csv");

  await expect(exportButton).toBeEnabled({ timeout: 15_000 });
  await expect(exportButton).toHaveText("Export CSV");
  await page.unroute(routePattern);
});

test("recalls export ZIP shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Recall",
    last_name: `Export Zip Hardening ${Date.now()}`,
  });
  const token = await ensureAuthReady(request);
  const dueDate = new Date().toISOString().slice(0, 10);
  const recallResponse = await request.post(`${baseUrl}/api/patients/${patientId}/recalls`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      kind: "exam",
      due_date: dueDate,
      notes: "Recall ZIP export hardening proof",
    },
  });
  expect(recallResponse.ok()).toBeTruthy();

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/recalls`, { waitUntil: "domcontentloaded" });

  const exportButton = page.getByTestId("recalls-export-zip");
  await expect(exportButton).toBeEnabled({ timeout: 15_000 });

  let seenRequest!: () => void;
  const seenRequestPromise = new Promise<void>((resolve) => {
    seenRequest = resolve;
  });
  let releaseResponse!: () => void;
  const releaseResponsePromise = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });
  let requestCount = 0;
  const routePattern = /\/api\/recalls\/letters\.zip\?/;

  await page.route(routePattern, async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    requestCount += 1;
    if (requestCount === 1) {
      seenRequest();
    }
    await releaseResponsePromise;
    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "application/zip",
        "Content-Disposition": 'attachment; filename="recall-letters-proof.zip"',
      },
      body: Buffer.from("zip export proof"),
    });
  });

  const downloadPromise = page.waitForEvent("download");
  await exportButton.click();
  await seenRequestPromise;

  await expect(exportButton).toBeDisabled();
  await expect(exportButton).toHaveText("Preparing...");
  await exportButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Recall export ZIP button not found");
    }
    button.click();
  });
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseResponse();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("recall-letters-proof.zip");

  await expect(exportButton).toBeEnabled({ timeout: 15_000 });
  await expect(exportButton).toHaveText("Download letters (ZIP)");
  await page.unroute(routePattern);
});
