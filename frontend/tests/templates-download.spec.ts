import { expect, test } from "@playwright/test";

import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

test("templates page download shows in-flight state and honors header filename", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  const token = await ensureAuthReady(request);

  const templateName = `Templates Page Download ${Date.now()}`;
  const templateResponse = await request.post(`${baseUrl}/api/document-templates`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name: templateName,
      kind: "letter",
      content: "Templates page proof",
      is_active: true,
    },
  });
  expect(templateResponse.ok()).toBeTruthy();
  const template = (await templateResponse.json()) as { id: number };

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/templates`, {
    waitUntil: "domcontentloaded",
  });

  await expect(page.getByTestId(`template-row-${template.id}`)).toBeVisible({
    timeout: 15_000,
  });
  const downloadButton = page.getByTestId(`template-download-${template.id}`);
  await expect(downloadButton).toBeVisible();

  const expectedFilename = `${templateName.replace(/[^A-Za-z0-9]+/g, "_").replace(/^_+|_+$/g, "")}-letter.txt`;
  const routePattern = new RegExp(`/api/document-templates/${template.id}/download$`);

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
        "Content-Type": "text/plain; charset=utf-8",
        "Content-Disposition": `attachment; filename="${expectedFilename}"`,
      },
      body: "templates download proof",
    });
  });

  const downloadPromise = page.waitForEvent("download");
  const clickState = await downloadButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Template download button not found");
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
  await expect(downloadButton).toBeDisabled();
  await expect(downloadButton).toHaveText("Downloading...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseResponse();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(expectedFilename);

  await expect(downloadButton).toBeEnabled({ timeout: 15_000 });
  await expect(downloadButton).toHaveText("Download");
  await page.unroute(routePattern);
});

test("templates page download falls back to backend filename contract without header", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  const token = await ensureAuthReady(request);

  const templateName = "Templates Page Fallback Proof";
  const templateResponse = await request.post(`${baseUrl}/api/document-templates`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name: templateName,
      kind: "letter",
      content: "Templates fallback proof",
      is_active: true,
    },
  });
  expect(templateResponse.ok()).toBeTruthy();
  const template = (await templateResponse.json()) as { id: number };

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/templates`, {
    waitUntil: "domcontentloaded",
  });

  await expect(page.getByTestId(`template-row-${template.id}`)).toBeVisible({
    timeout: 15_000,
  });
  const downloadButton = page.getByTestId(`template-download-${template.id}`);
  await expect(downloadButton).toBeVisible();

  const expectedFilename = "Templates_Page_Fallback_Proof-letter.txt";
  const routePattern = new RegExp(`/api/document-templates/${template.id}/download$`);

  let seenRequest!: () => void;
  const seenRequestPromise = new Promise<void>((resolve) => {
    seenRequest = resolve;
  });
  let releaseResponse!: () => void;
  const releaseResponsePromise = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });

  await page.route(routePattern, async (route) => {
    seenRequest();
    await releaseResponsePromise;
    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "text/plain; charset=utf-8",
      },
      body: "templates fallback proof",
    });
  });

  const downloadPromise = page.waitForEvent("download");
  await downloadButton.click();
  await seenRequestPromise;

  await expect(downloadButton).toBeDisabled();
  await expect(downloadButton).toHaveText("Downloading...");

  releaseResponse();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(expectedFilename);

  await expect(downloadButton).toBeEnabled({ timeout: 15_000 });
  await expect(downloadButton).toHaveText("Download");
  await page.unroute(routePattern);
});

test("templates page selected-template detail download reuses hardened download behavior", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  const token = await ensureAuthReady(request);

  const templateName = `Templates Detail Download ${Date.now()}`;
  const templateResponse = await request.post(`${baseUrl}/api/document-templates`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name: templateName,
      kind: "letter",
      content: "Templates detail proof",
      is_active: true,
    },
  });
  expect(templateResponse.ok()).toBeTruthy();
  const template = (await templateResponse.json()) as { id: number };

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/templates`, {
    waitUntil: "domcontentloaded",
  });

  const row = page.getByTestId(`template-row-${template.id}`);
  await expect(row).toBeVisible({ timeout: 15_000 });
  await row.getByRole("button", { name: templateName }).click();

  const detailDownloadButton = page.getByTestId("template-detail-download");
  await expect(detailDownloadButton).toBeVisible();

  const expectedFilename = `${templateName.replace(/[^A-Za-z0-9]+/g, "_").replace(/^_+|_+$/g, "")}-letter.txt`;
  const routePattern = new RegExp(`/api/document-templates/${template.id}/download$`);

  let seenRequest!: () => void;
  const seenRequestPromise = new Promise<void>((resolve) => {
    seenRequest = resolve;
  });
  let releaseResponse!: () => void;
  const releaseResponsePromise = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });

  await page.route(routePattern, async (route) => {
    seenRequest();
    await releaseResponsePromise;
    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "text/plain; charset=utf-8",
        "Content-Disposition": `attachment; filename="${expectedFilename}"`,
      },
      body: "templates detail download proof",
    });
  });

  const downloadPromise = page.waitForEvent("download");
  await detailDownloadButton.click();
  await seenRequestPromise;

  await expect(detailDownloadButton).toBeDisabled();
  await expect(detailDownloadButton).toHaveText("Downloading...");

  releaseResponse();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(expectedFilename);

  await expect(detailDownloadButton).toBeEnabled({ timeout: 15_000 });
  await expect(detailDownloadButton).toHaveText("Download");
  await page.unroute(routePattern);
});
