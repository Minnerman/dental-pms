import { expect, test } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

test("patient estimate PDF download shows in-flight state and honors header filename", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Estimate",
    last_name: "PdfHardening",
  });
  const token = await ensureAuthReady(request);

  const estimateResponse = await request.post(`${baseUrl}/api/patients/${patientId}/estimates`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      notes: "Estimate PDF hardening proof",
    },
  });
  expect(estimateResponse.ok()).toBeTruthy();
  const estimate = (await estimateResponse.json()) as { id: number };

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${patientId}`, {
    waitUntil: "domcontentloaded",
  });

  await page.getByTestId("patient-tab-Treatment").click();

  const viewButton = page.getByTestId(`estimate-view-${estimate.id}`);
  await expect(viewButton).toBeVisible({ timeout: 15_000 });
  await viewButton.click();

  const downloadButton = page.getByTestId(`estimate-download-pdf-${estimate.id}`);
  await expect(downloadButton).toBeVisible({ timeout: 15_000 });

  const expectedFilename = `estimate-${estimate.id}.pdf`;
  const routePattern = new RegExp(`/api/estimates/${estimate.id}/pdf$`);

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
  await page.evaluate((estimateId) => {
    const button = document.querySelector(
      `[data-testid="estimate-download-pdf-${estimateId}"]`
    );
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Estimate PDF download button not found");
    }
    button.click();
  }, estimate.id);
  await seenRequestPromise;

  await expect(downloadButton).toBeDisabled();
  await expect(downloadButton).toHaveText("Downloading PDF...");

  releaseResponse();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(expectedFilename);

  await expect(downloadButton).toBeEnabled({ timeout: 15_000 });
  await expect(downloadButton).toHaveText("Download PDF");
  await page.unroute(routePattern);
});
