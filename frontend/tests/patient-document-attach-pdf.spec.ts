import { expect, test } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

test("patient document Save PDF to attachments shows in-flight state and success notice", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Document",
    last_name: "AttachProof",
  });
  const token = await ensureAuthReady(request);

  const templateResponse = await request.post(`${baseUrl}/api/document-templates`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name: `Patient Attach Template ${Date.now()}`,
      kind: "letter",
      content: "Attach body for {{patient.full_name}}",
      is_active: true,
    },
  });
  expect(templateResponse.ok()).toBeTruthy();
  const template = (await templateResponse.json()) as { id: number };

  const documentTitle = "Patient Attach Proof";
  const documentResponse = await request.post(`${baseUrl}/api/patients/${patientId}/documents`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      template_id: template.id,
      title: documentTitle,
    },
  });
  expect(documentResponse.ok()).toBeTruthy();
  const patientDocument = (await documentResponse.json()) as { id: number };

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${patientId}/documents`, {
    waitUntil: "domcontentloaded",
  });

  const attachButton = page.getByTestId(`patient-document-attach-pdf-${patientDocument.id}`);
  await expect(page.getByTestId(`patient-document-card-${patientDocument.id}`)).toBeVisible({
    timeout: 15_000,
  });
  await expect(attachButton).toBeVisible();

  const routePattern = new RegExp(`/api/patient-documents/${patientDocument.id}/attach-pdf$`);

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
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        id: 99_001,
        patient_id: Number(patientId),
        original_filename: "Patient_Attach_Proof.pdf",
        content_type: "application/pdf",
        byte_size: 1234,
      }),
    });
  });

  const clickState = await page.evaluate((id) => {
    const button = document.querySelector(`[data-testid="patient-document-attach-pdf-${id}"]`);
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Attach PDF button not found");
    }
    const beforeDisabled = button.disabled;
    button.click();
    const afterFirstDisabled = button.disabled;
    button.click();
    return { beforeDisabled, afterFirstDisabled, afterSecondDisabled: button.disabled };
  }, patientDocument.id);
  await seenRequestPromise;

  expect(clickState.beforeDisabled).toBe(false);
  expect(clickState.afterFirstDisabled).toBe(true);
  expect(clickState.afterSecondDisabled).toBe(true);
  await expect(attachButton).toBeDisabled();
  await expect(attachButton).toHaveText("Saving PDF...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseResponse();

  await expect(page.getByText("PDF saved to attachments.", { exact: true })).toBeVisible({
    timeout: 15_000,
  });
  await expect(attachButton).toBeEnabled({ timeout: 15_000 });
  await expect(attachButton).toHaveText("Save PDF to attachments");
  await page.unroute(routePattern);
});
