import { expect, test } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

const chartingEnabled = process.env.NEXT_PUBLIC_FEATURE_CHARTING_VIEWER === "1";

test("patient charting export shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  test.skip(!chartingEnabled, "charting viewer disabled");
  const configRes = await request.get(`${baseUrl}/api/config`);
  const config = (await configRes.json()) as {
    feature_flags?: { charting_viewer?: boolean };
  };
  test.skip(!config?.feature_flags?.charting_viewer, "charting viewer disabled");
  const patientId = await createPatient(request, {
    first_name: "Charting",
    last_name: "ExportGuard",
  });

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${patientId}/charting`, {
    waitUntil: "domcontentloaded",
  });

  await expect(page).toHaveURL(new RegExp(`/patients/${patientId}/charting`));
  await expect(page.getByTestId("charting-viewer")).toBeVisible({ timeout: 15_000 });

  const exportButton = page.getByTestId("charting-export-csv");
  await expect(exportButton).toBeVisible({ timeout: 15_000 });

  const expectedFilename = `charting-${patientId}-export.zip`;
  const routePattern = new RegExp(`/api/patients/${patientId}/charting/export\\?`);

  let seenRequest!: () => void;
  const seenRequestPromise = new Promise<void>((resolve) => {
    seenRequest = resolve;
  });
  let releaseResponse!: () => void;
  const releaseResponsePromise = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });
  let requestCount = 0;

  await page.route(routePattern, async (route) => {
    requestCount += 1;
    if (requestCount === 1) {
      seenRequest();
    }
    await releaseResponsePromise;
    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "application/zip",
        "Content-Disposition": `attachment; filename="${expectedFilename}"`,
      },
      body: Buffer.from("PK\x03\x04charting-export"),
    });
  });

  const downloadPromise = page.waitForEvent("download");
  const clickState = await page.evaluate(() => {
    const button = document.querySelector('[data-testid="charting-export-csv"]');
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Charting export button not found");
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
  expect(download.suggestedFilename()).toBe(expectedFilename);

  await expect(exportButton).toBeEnabled({ timeout: 15_000 });
  await expect(exportButton).toHaveText("Export CSV");
  await page.unroute(routePattern);
});

test("patient charting review pack shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  test.skip(!chartingEnabled, "charting viewer disabled");
  const configRes = await request.get(`${baseUrl}/api/config`);
  const config = (await configRes.json()) as {
    feature_flags?: { charting_viewer?: boolean };
  };
  test.skip(!config?.feature_flags?.charting_viewer, "charting viewer disabled");
  const patientId = await createPatient(request, {
    first_name: "Charting",
    last_name: "ReviewPackGuard",
  });

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${patientId}/charting`, {
    waitUntil: "domcontentloaded",
  });

  await expect(page).toHaveURL(new RegExp(`/patients/${patientId}/charting`));
  await expect(page.getByTestId("charting-viewer")).toBeVisible({ timeout: 15_000 });

  const reviewPackButton = page.getByTestId("charting-review-pack-generate");
  await expect(reviewPackButton).toBeVisible({ timeout: 15_000 });

  const expectedFilename = `charting-review-pack-${patientId}.zip`;
  const routePattern = new RegExp(`/api/patients/${patientId}/charting/export\\?`);

  let seenRequest!: () => void;
  const seenRequestPromise = new Promise<void>((resolve) => {
    seenRequest = resolve;
  });
  let releaseResponse!: () => void;
  const releaseResponsePromise = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });
  let requestCount = 0;
  let seenUrl = "";

  await page.route(routePattern, async (route) => {
    requestCount += 1;
    seenUrl = decodeURIComponent(route.request().url());
    if (requestCount === 1) {
      seenRequest();
    }
    await releaseResponsePromise;
    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "application/zip",
        "Content-Disposition": `attachment; filename="${expectedFilename}"`,
      },
      body: Buffer.from("PK\x03\x04charting-review-pack"),
    });
  });

  const downloadPromise = page.waitForEvent("download");
  const clickState = await page.evaluate(() => {
    const button = document.querySelector('[data-testid="charting-review-pack-generate"]');
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Charting review-pack button not found");
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
  expect(seenUrl).toContain(
    "entities=perio_probes,bpe,bpe_furcations,patient_notes,tooth_surfaces"
  );
  await expect(reviewPackButton).toBeDisabled();
  await expect(reviewPackButton).toHaveText("Generating...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseResponse();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(expectedFilename);

  await expect(page.getByText("Review pack ready. Share links exclude text search by default."))
    .toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Review pack links")).toBeVisible();
  const reviewPackLinks = await page.locator("input.input").evaluateAll((elements) =>
    elements.map((element) => (element as HTMLInputElement).value)
  );
  expect(
    reviewPackLinks.filter((value) => value.includes(`/patients/${patientId}/charting?`))
      .length
  ).toBe(4);
  await expect(reviewPackButton).toBeEnabled({ timeout: 15_000 });
  await expect(reviewPackButton).toHaveText("Generate review pack");
  await page.unroute(routePattern);
});
