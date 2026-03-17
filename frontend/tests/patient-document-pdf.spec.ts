import { expect, test } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

test("patient document PDF download shows in-flight state and honors header filename", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Document",
    last_name: "PdfHardening",
  });
  const token = await ensureAuthReady(request);
  const today = new Date().toISOString().slice(0, 10);

  const templateResponse = await request.post(`${baseUrl}/api/document-templates`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name: `Patient PDF Template ${Date.now()}`,
      kind: "letter",
      content: "PDF body for {{patient.full_name}}",
      is_active: true,
    },
  });
  expect(templateResponse.ok()).toBeTruthy();
  const template = (await templateResponse.json()) as { id: number };

  const documentTitle = "Patient PDF Hardening";
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

  const pdfButton = page.getByTestId(`patient-document-download-pdf-${document.id}`);
  await expect(page.getByTestId(`patient-document-card-${document.id}`)).toBeVisible({
    timeout: 15_000,
  });
  await expect(pdfButton).toBeVisible();

  const expectedFilename = `Patient_PDF_Hardening_PdfHardening_${today}.pdf`;
  const routePattern = new RegExp(`/api/patient-documents/${document.id}/download\\?format=pdf$`);

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
        "Content-Type": "application/pdf",
        "Content-Disposition": `attachment; filename="${expectedFilename}"`,
      },
      body: Buffer.from("%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"),
    });
  });

  const downloadPromise = page.waitForEvent("download");
  await pdfButton.click();
  await seenRequestPromise;

  await expect(pdfButton).toBeDisabled();
  await expect(pdfButton).toHaveText("Downloading PDF...");

  releaseResponse();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(expectedFilename);

  await expect(pdfButton).toBeEnabled({ timeout: 15_000 });
  await expect(pdfButton).toHaveText("Download PDF");
  await page.unroute(routePattern);
});

test("patient document PDF download falls back to patient-aware filename without header", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Document",
    last_name: "PdfFallback",
  });
  const token = await ensureAuthReady(request);
  const today = new Date().toISOString().slice(0, 10);

  const templateResponse = await request.post(`${baseUrl}/api/document-templates`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name: `Patient PDF Fallback Template ${Date.now()}`,
      kind: "letter",
      content: "PDF body for {{patient.full_name}}",
      is_active: true,
    },
  });
  expect(templateResponse.ok()).toBeTruthy();
  const template = (await templateResponse.json()) as { id: number };

  const documentTitle = "Patient PDF Fallback / Proof";
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

  const pdfButton = page.getByTestId(`patient-document-download-pdf-${document.id}`);
  await expect(page.getByTestId(`patient-document-card-${document.id}`)).toBeVisible({
    timeout: 15_000,
  });
  await expect(pdfButton).toBeVisible();

  const expectedFilename = `Patient_PDF_Fallback_Proof_PdfFallback_${today}.pdf`;
  const routePattern = new RegExp(`/api/patient-documents/${document.id}/download\\?format=pdf$`);

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
        "Content-Type": "application/pdf",
      },
      body: Buffer.from("%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"),
    });
  });

  const downloadPromise = page.waitForEvent("download");
  await pdfButton.click();
  await seenRequestPromise;

  await expect(pdfButton).toBeDisabled();
  await expect(pdfButton).toHaveText("Downloading PDF...");

  releaseResponse();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(expectedFilename);

  await expect(pdfButton).toBeEnabled({ timeout: 15_000 });
  await expect(pdfButton).toHaveText("Download PDF");
  await page.unroute(routePattern);
});
