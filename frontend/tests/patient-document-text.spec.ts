import { expect, test } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

test("patient document text download shows in-flight state and honors header filename", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Document",
    last_name: "TextHardening",
  });
  const token = await ensureAuthReady(request);
  const today = new Date().toISOString().slice(0, 10);

  const templateResponse = await request.post(`${baseUrl}/api/document-templates`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name: `Patient Text Template ${Date.now()}`,
      kind: "letter",
      content: "Text body for {{patient.full_name}}",
      is_active: true,
    },
  });
  expect(templateResponse.ok()).toBeTruthy();
  const template = (await templateResponse.json()) as { id: number };

  const documentTitle = "Patient Text Hardening";
  const documentResponse = await request.post(`${baseUrl}/api/patients/${patientId}/documents`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      template_id: template.id,
      title: documentTitle,
    },
  });
  expect(documentResponse.ok()).toBeTruthy();
  const document = (await documentResponse.json()) as { id: number };

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${patientId}/documents`, {
    waitUntil: "domcontentloaded",
  });

  const textButton = page.getByTestId(`patient-document-download-text-${document.id}`);
  await expect(page.getByTestId(`patient-document-card-${document.id}`)).toBeVisible({
    timeout: 15_000,
  });
  await expect(textButton).toBeVisible();

  const expectedFilename = `Patient_Text_Hardening_TextHardening_${today}.txt`;
  const routePattern = new RegExp(`/api/patient-documents/${document.id}/download$`);

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
      body: "text hardening proof",
    });
  });

  const downloadPromise = page.waitForEvent("download");
  await textButton.click();
  await seenRequestPromise;

  await expect(textButton).toBeDisabled();
  await expect(textButton).toHaveText("Downloading text...");

  releaseResponse();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(expectedFilename);

  await expect(textButton).toBeEnabled({ timeout: 15_000 });
  await expect(textButton).toHaveText("Download text");
  await page.unroute(routePattern);
});

test("patient document text download falls back to patient-aware filename without header", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Document",
    last_name: "TextFallback",
  });
  const token = await ensureAuthReady(request);
  const serverDateHeader = "Wed, 18 Mar 2026 00:30:00 GMT";
  const expectedDate = "2026-03-18";

  const templateResponse = await request.post(`${baseUrl}/api/document-templates`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name: `Patient Text Fallback Template ${Date.now()}`,
      kind: "letter",
      content: "Text body for {{patient.full_name}}",
      is_active: true,
    },
  });
  expect(templateResponse.ok()).toBeTruthy();
  const template = (await templateResponse.json()) as { id: number };

  const documentTitle = "Patient Text Fallback / Proof";
  const documentResponse = await request.post(`${baseUrl}/api/patients/${patientId}/documents`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      template_id: template.id,
      title: documentTitle,
    },
  });
  expect(documentResponse.ok()).toBeTruthy();
  const document = (await documentResponse.json()) as { id: number };

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${patientId}/documents`, {
    waitUntil: "domcontentloaded",
  });

  const textButton = page.getByTestId(`patient-document-download-text-${document.id}`);
  await expect(page.getByTestId(`patient-document-card-${document.id}`)).toBeVisible({
    timeout: 15_000,
  });
  await expect(textButton).toBeVisible();

  const expectedFilename = `Patient_Text_Fallback_Proof_TextFallback_${expectedDate}.txt`;
  const routePattern = new RegExp(`/api/patient-documents/${document.id}/download$`);

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
        Date: serverDateHeader,
      },
      body: "text fallback proof",
    });
  });

  const downloadPromise = page.waitForEvent("download");
  await textButton.click();
  await seenRequestPromise;

  await expect(textButton).toBeDisabled();
  await expect(textButton).toHaveText("Downloading text...");

  releaseResponse();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(expectedFilename);

  await expect(textButton).toBeEnabled({ timeout: 15_000 });
  await expect(textButton).toHaveText("Download text");
  await page.unroute(routePattern);
});
