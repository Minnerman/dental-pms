import { expect, test, type Page } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

async function waitForPatientPage(page: Page, patientId: string) {
  await expect(page).toHaveURL(new RegExp(`/patients/${patientId}/clinical`));
  await expect(page.getByTestId("patient-tabs")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Loading patient…")).toHaveCount(0);
}

test("patient recall letter download honors header filename on the patient page", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Recall",
    last_name: "Parity",
  });
  const token = await ensureAuthReady(request);
  const recallNotes = `Patient recall parity ${Date.now()}`;
  const dueDate = "2026-04-15";

  const recallResponse = await request.post(`${baseUrl}/api/patients/${patientId}/recalls`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      kind: "exam",
      due_date: dueDate,
      status: "upcoming",
      notes: recallNotes,
    },
  });
  expect(recallResponse.ok()).toBeTruthy();
  const recall = (await recallResponse.json()) as { id: number };

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${patientId}/clinical`, {
    waitUntil: "domcontentloaded",
  });
  await waitForPatientPage(page, patientId);

  await page.getByTestId("patient-tab-Schemes").click();
  await expect(page.getByTestId("patient-tab-Schemes")).toHaveAttribute(
    "aria-selected",
    "true"
  );

  const recallRow = page.locator(".recall-table tbody tr").filter({ hasText: recallNotes }).first();
  await expect(recallRow).toBeVisible({ timeout: 15_000 });
  const generateButton = recallRow
    .locator("button")
    .filter({ hasText: /Generate letter|Generating\.\.\./ })
    .first();
  await expect(generateButton).toBeVisible();

  const expectedFilename = `recall-${patientId}-${recall.id}.pdf`;
  const routePattern = new RegExp(
    `/api/patients/${patientId}/recalls/${recall.id}/letter\\.pdf$`
  );

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
  await generateButton.click();
  await seenRequestPromise;

  await expect(generateButton).toBeDisabled();
  await expect(generateButton).toHaveText("Generating...");

  releaseResponse();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(expectedFilename);

  await expect(generateButton).toBeEnabled({ timeout: 15_000 });
  await expect(generateButton).toHaveText("Generate letter");
  await page.unroute(routePattern);
});
