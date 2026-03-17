import { expect, test } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

test("patient document preview disables in-flight and guards repeat submit", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Document",
    last_name: "PreviewProof",
  });
  const token = await ensureAuthReady(request);

  const templateName = `Patient Preview Template ${Date.now()}`;
  const templateResponse = await request.post(`${baseUrl}/api/document-templates`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name: templateName,
      kind: "letter",
      content: "Preview body for {{patient.full_name}}",
      is_active: true,
    },
  });
  expect(templateResponse.ok()).toBeTruthy();
  const template = (await templateResponse.json()) as { id: number };

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${patientId}/documents`, {
    waitUntil: "domcontentloaded",
  });

  await page.getByTestId("patient-document-template-select").selectOption(String(template.id));
  await page.getByTestId("patient-document-title-input").fill("Patient Preview Proof");

  const previewButton = page.getByTestId("patient-document-preview");
  await expect(previewButton).toBeVisible();

  let requestCount = 0;
  let seenRequest!: () => void;
  const seenRequestPromise = new Promise<void>((resolve) => {
    seenRequest = resolve;
  });
  let releaseResponse!: () => void;
  const releaseResponsePromise = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });
  const routePattern = new RegExp(`/api/patients/${patientId}/documents/preview$`);

  await page.route(routePattern, async (route) => {
    requestCount += 1;
    if (requestCount === 1) {
      seenRequest();
    }
    await releaseResponsePromise;
    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        title: "Patient Preview Proof",
        rendered_content: "Preview body for Document PreviewProof",
        unknown_fields: [],
      }),
    });
  });

  await page.evaluate(() => {
    const button = document.querySelector('[data-testid="patient-document-preview"]');
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Preview button not found");
    }
    button.click();
    button.click();
  });
  await seenRequestPromise;

  await expect(previewButton).toBeDisabled();
  await expect(previewButton).toHaveText("Rendering...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseResponse();

  const previewOutput = page.locator("textarea[readonly]");
  await expect(previewOutput).toHaveValue("Preview body for Document PreviewProof", {
    timeout: 15_000,
  });
  await expect(previewButton).toBeEnabled({ timeout: 15_000 });
  await expect(previewButton).toHaveText("Preview");

  await page.unroute(routePattern);
});
