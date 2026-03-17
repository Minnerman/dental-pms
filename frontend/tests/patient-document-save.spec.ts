import { expect, test } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

test("patient document save disables in-flight and guards repeat submit", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Document",
    last_name: "SaveProof",
  });
  const token = await ensureAuthReady(request);

  const templateName = `Patient Save Template ${Date.now()}`;
  const templateResponse = await request.post(`${baseUrl}/api/document-templates`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name: templateName,
      kind: "letter",
      content: "Save body for {{patient.full_name}}",
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
  const titleInput = page.getByTestId("patient-document-title-input");
  const documentTitle = "Patient Save Proof";
  await titleInput.fill(documentTitle);

  const saveButton = page.getByTestId("patient-document-save");
  await expect(saveButton).toBeVisible();

  let requestCount = 0;
  let seenRequest!: () => void;
  const seenRequestPromise = new Promise<void>((resolve) => {
    seenRequest = resolve;
  });
  let releaseResponse!: () => void;
  const releaseResponsePromise = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });
  const routePattern = new RegExp(`/api/patients/${patientId}/documents$`);

  await page.route(routePattern, async (route) => {
    requestCount += 1;
    if (requestCount === 1) {
      seenRequest();
    }
    await releaseResponsePromise;
    await route.continue();
  });

  await page.evaluate(() => {
    const button = document.querySelector('[data-testid="patient-document-save"]');
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Save button not found");
    }
    button.click();
    button.click();
  });
  await seenRequestPromise;

  await expect(saveButton).toBeDisabled();
  await expect(saveButton).toHaveText("Saving...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseResponse();

  await expect(saveButton).toBeEnabled({ timeout: 15_000 });
  await expect(saveButton).toHaveText("Save document");
  await expect
    .poll(
      async () => {
        const response = await request.get(`${baseUrl}/api/patients/${patientId}/documents`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        expect(response.ok()).toBeTruthy();
        const documents = (await response.json()) as { title: string }[];
        return documents.filter((item) => item.title === documentTitle).length;
      },
      { timeout: 15_000 }
    )
    .toBe(1);

  await page.unroute(routePattern);
});
