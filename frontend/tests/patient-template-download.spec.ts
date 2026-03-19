import { expect, test } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

test("patient-page template download shows in-flight state and honors header filename", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Template",
    last_name: "DownloadProof",
  });
  const token = await ensureAuthReady(request);

  const templateName = "Patient Template Download";
  const templateResponse = await request.post(`${baseUrl}/api/document-templates`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name: templateName,
      kind: "letter",
      content: "Template body for {{patient.full_name}}",
      is_active: true,
    },
  });
  expect(templateResponse.ok()).toBeTruthy();
  const template = (await templateResponse.json()) as { id: number };

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${patientId}/documents`, {
    waitUntil: "domcontentloaded",
  });

  await expect(page.getByTestId(`patient-template-card-${template.id}`)).toBeVisible({
    timeout: 15_000,
  });
  const downloadButton = page.getByTestId(`patient-template-download-${template.id}`);
  await expect(downloadButton).toBeVisible();

  const expectedFilename = "Patient_Template_Download-letter.txt";
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
      body: "patient template download proof",
    });
  });

  const downloadPromise = page.waitForEvent("download");
  const clickState = await page.evaluate((id) => {
    const button = document.querySelector(`[data-testid="patient-template-download-${id}"]`);
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Template download button not found");
    }
    const beforeDisabled = button.disabled;
    button.click();
    const afterFirstDisabled = button.disabled;
    button.click();
    return { beforeDisabled, afterFirstDisabled, afterSecondDisabled: button.disabled };
  }, template.id);
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

test("patient-page template download falls back to backend filename contract without header", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Template",
    last_name: "FallbackProof",
  });
  const token = await ensureAuthReady(request);

  const templateName = "Patient Template Fallback Proof";
  const templateResponse = await request.post(`${baseUrl}/api/document-templates`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name: templateName,
      kind: "letter",
      content: "Template fallback proof for {{patient.full_name}}",
      is_active: true,
    },
  });
  expect(templateResponse.ok()).toBeTruthy();
  const template = (await templateResponse.json()) as { id: number };

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${patientId}/documents`, {
    waitUntil: "domcontentloaded",
  });

  await expect(page.getByTestId(`patient-template-card-${template.id}`)).toBeVisible({
    timeout: 15_000,
  });
  const downloadButton = page.getByTestId(`patient-template-download-${template.id}`);
  await expect(downloadButton).toBeVisible();

  const expectedFilename = "Patient_Template_Fallback_Proof-letter.txt";
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
      body: "patient template fallback proof",
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
