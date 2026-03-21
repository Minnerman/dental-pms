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
        "Content-Type": "application/pdf",
        "Content-Disposition": `attachment; filename="${expectedFilename}"`,
      },
      body: Buffer.from("%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"),
    });
  });

  const downloadPromise = page.waitForEvent("download");
  const clickState = await page.evaluate((estimateId) => {
    const button = document.querySelector(
      `[data-testid="estimate-download-pdf-${estimateId}"]`
    );
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Estimate PDF download button not found");
    }
    const beforeDisabled = button.disabled;
    button.click();
    const afterFirstDisabled = button.disabled;
    button.click();
    return { beforeDisabled, afterFirstDisabled, afterSecondDisabled: button.disabled };
  }, estimate.id);
  await seenRequestPromise;

  expect(clickState.beforeDisabled).toBe(false);
  expect(clickState.afterFirstDisabled).toBe(true);
  expect(clickState.afterSecondDisabled).toBe(true);
  await expect(downloadButton).toBeDisabled();
  await expect(downloadButton).toHaveText("Downloading PDF...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseResponse();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(expectedFilename);

  await expect(downloadButton).toBeEnabled({ timeout: 15_000 });
  await expect(downloadButton).toHaveText("Download PDF");
  await page.unroute(routePattern);
});

test("patient estimate create shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Estimate",
    last_name: `CreateHardening${unique}`,
  });
  const token = await primePageAuth(page, request);
  const notes = `Estimate create proof ${unique}`;
  const validUntil = "2026-12-31";

  await page.goto(`${baseUrl}/patients/${patientId}`, {
    waitUntil: "domcontentloaded",
  });
  await page.getByTestId("patient-tab-Treatment").click();

  await page.getByTestId("patient-estimate-valid-until").fill(validUntil);
  await page.getByTestId("patient-estimate-notes").fill(notes);

  const createButton = page.getByTestId("patient-estimate-create");
  await expect(createButton).toBeEnabled();

  let requestCount = 0;
  const routePattern = new RegExp(`/api/patients/${patientId}/estimates$`);
  let seenRequest!: () => void;
  const seenRequestPromise = new Promise<void>((resolve) => {
    seenRequest = resolve;
  });
  let releaseResponse!: () => void;
  const releaseResponsePromise = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });
  await page.route(routePattern, async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    requestCount += 1;
    if (requestCount === 1) {
      seenRequest();
      await releaseResponsePromise;
    }
    await route.continue();
  });
  const estimateResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().includes(`/api/patients/${patientId}/estimates`)
  );

  const clickState = await createButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Create estimate button not found");
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
  await expect(createButton).toBeDisabled();
  await expect(createButton).toHaveText("Creating...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseResponse();

  const estimateResponse = await estimateResponsePromise;
  expect(estimateResponse.ok()).toBeTruthy();
  expect(estimateResponse.request().postDataJSON()).toMatchObject({
    notes,
    valid_until: validUntil,
  });
  await page.unroute(routePattern);

  await expect(createButton).toHaveText("Create estimate", { timeout: 15_000 });
  await expect(createButton).toBeEnabled();

  const verifyResponse = await request.get(`${baseUrl}/api/patients/${patientId}/estimates`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(verifyResponse.ok()).toBeTruthy();
  const estimates = (await verifyResponse.json()) as Array<{
    notes: string | null;
    valid_until: string | null;
  }>;
  expect(
    estimates.some(
      (estimate) =>
        estimate.notes === notes && estimate.valid_until?.slice(0, 10) === validUntil
    )
  ).toBeTruthy();
});

test("patient estimate status save shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Estimate",
    last_name: `StatusHardening${unique}`,
  });
  const token = await primePageAuth(page, request);

  const createResponse = await request.post(`${baseUrl}/api/patients/${patientId}/estimates`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      notes: `Estimate status proof ${unique}`,
    },
  });
  expect(createResponse.ok()).toBeTruthy();
  const estimate = (await createResponse.json()) as { id: number };

  await page.goto(`${baseUrl}/patients/${patientId}`, {
    waitUntil: "domcontentloaded",
  });
  await page.getByTestId("patient-tab-Treatment").click();

  const viewButton = page.getByTestId(`estimate-view-${estimate.id}`);
  await expect(viewButton).toBeVisible({ timeout: 15_000 });
  await viewButton.click();

  const issuedButton = page.getByTestId(`estimate-status-${estimate.id}-issued`);
  await expect(issuedButton).toBeEnabled({ timeout: 15_000 });

  let requestCount = 0;
  const routePattern = new RegExp(`/api/estimates/${estimate.id}$`);
  let seenRequest!: () => void;
  const seenRequestPromise = new Promise<void>((resolve) => {
    seenRequest = resolve;
  });
  let releaseResponse!: () => void;
  const releaseResponsePromise = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });
  await page.route(routePattern, async (route) => {
    if (route.request().method() !== "PATCH") {
      await route.continue();
      return;
    }
    requestCount += 1;
    if (requestCount === 1) {
      seenRequest();
      await releaseResponsePromise;
    }
    await route.continue();
  });
  const statusResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      response.url().includes(`/api/estimates/${estimate.id}`)
  );

  const clickState = await issuedButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Estimate status button not found");
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
  await expect(issuedButton).toBeDisabled();
  await expect(issuedButton).toHaveText("Updating...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseResponse();

  const statusResponse = await statusResponsePromise;
  expect(statusResponse.ok()).toBeTruthy();
  expect(statusResponse.request().postDataJSON()).toMatchObject({
    status: "ISSUED",
  });
  await page.unroute(routePattern);

  await expect(issuedButton).toHaveText("Mark issued", { timeout: 15_000 });
  await expect(issuedButton).toBeEnabled();

  const verifyResponse = await request.get(`${baseUrl}/api/estimates/${estimate.id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(verifyResponse.ok()).toBeTruthy();
  const updatedEstimate = (await verifyResponse.json()) as { status: string };
  expect(updatedEstimate.status).toBe("ISSUED");
});
