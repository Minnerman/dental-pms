import { expect, test } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

test("patient document delete shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Document",
    last_name: "DeleteProof",
  });
  const token = await ensureAuthReady(request);

  const templateResponse = await request.post(`${baseUrl}/api/document-templates`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name: `Patient Delete Template ${Date.now()}`,
      kind: "letter",
      content: "Delete body for {{patient.full_name}}",
      is_active: true,
    },
  });
  expect(templateResponse.ok()).toBeTruthy();
  const template = (await templateResponse.json()) as { id: number };

  const documentResponse = await request.post(`${baseUrl}/api/patients/${patientId}/documents`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      template_id: template.id,
      title: "Patient Delete Proof",
    },
  });
  expect(documentResponse.ok()).toBeTruthy();
  const patientDocument = (await documentResponse.json()) as { id: number };

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${patientId}/documents`, {
    waitUntil: "domcontentloaded",
  });

  const row = page.getByTestId(`patient-document-card-${patientDocument.id}`);
  const deleteButton = page.getByTestId(`patient-document-delete-${patientDocument.id}`);
  await expect(row).toBeVisible({ timeout: 15_000 });
  await expect(deleteButton).toBeVisible();

  await page.evaluate(() => {
    window.confirm = () => true;
  });

  let requestCount = 0;
  let seenRequest!: () => void;
  const seenRequestPromise = new Promise<void>((resolve) => {
    seenRequest = resolve;
  });
  let releaseResponse!: () => void;
  const releaseResponsePromise = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });
  const routePattern = new RegExp(`/api/patient-documents/${patientDocument.id}$`);

  await page.route(routePattern, async (route, routedRequest) => {
    if (routedRequest.method() !== "DELETE") {
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
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        id: patientDocument.id,
        patient_id: Number(patientId),
        title: "Patient Delete Proof",
        rendered_content: "Delete body for Document DeleteProof",
        template_id: template.id,
        created_at: "2026-03-19T12:34:56Z",
        created_by: {
          id: 1,
          email: "admin@example.com",
          role: "superadmin",
        },
      }),
    });
  });

  const clickState = await page.evaluate((id) => {
    const button = document.querySelector(`[data-testid="patient-document-delete-${id}"]`);
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Delete button not found");
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
  await expect(deleteButton).toBeDisabled();
  await expect(deleteButton).toHaveText("Deleting...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseResponse();

  await expect(row).toHaveCount(0);
  await page.unroute(routePattern);
});
