import { expect, test } from "@playwright/test";

import { addInvoiceLine, createInvoice, createPatient, issueInvoice } from "./helpers/api";
import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

test("recording a payment updates status and enables receipt download", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Billing",
    last_name: `Test ${Date.now()}`,
  });
  const invoice = await createInvoice(request, patientId);
  await addInvoiceLine(request, invoice.id, {
    description: "Exam",
    quantity: 1,
    unit_price_pence: 2500,
  });
  const issued = await issueInvoice(request, invoice.id);

  await primePageAuth(page, request);
  await page.goto(`${getBaseUrl()}/patients/${patientId}`, { waitUntil: "domcontentloaded" });

  await page.getByTestId("patient-tab-Financial").click();

  const invoiceRow = page.locator("tr", { hasText: issued.invoice_number });
  await expect(invoiceRow).toBeVisible({ timeout: 15_000 });
  await invoiceRow.getByRole("button", { name: "View" }).click();

  const recordButton = page.getByTestId("record-payment");
  await expect(recordButton).toBeVisible({ timeout: 15_000 });
  await expect(recordButton).toBeEnabled();

  await page.getByTestId("payment-amount").fill("25.00");
  let paymentRequestCount = 0;
  const paymentRoutePattern = new RegExp(`/api/invoices/${invoice.id}/payments$`);
  let seenPaymentRequest!: () => void;
  const seenPaymentRequestPromise = new Promise<void>((resolve) => {
    seenPaymentRequest = resolve;
  });
  let releasePaymentRequest!: () => void;
  const releasePaymentRequestPromise = new Promise<void>((resolve) => {
    releasePaymentRequest = resolve;
  });
  await page.route(paymentRoutePattern, async (route) => {
    paymentRequestCount += 1;
    if (paymentRequestCount === 1) {
      seenPaymentRequest();
      await releasePaymentRequestPromise;
    }
    await route.continue();
  });
  const paymentResponsePromise = page.waitForResponse((response) => {
    return (
      response.request().method() === "POST" &&
      response.url().endsWith(`/api/invoices/${invoice.id}/payments`)
    );
  });
  const paymentClickState = await page.evaluate(() => {
    const button = document.querySelector('[data-testid="record-payment"]');
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Record payment button not found");
    }
    const beforeDisabled = button.disabled;
    button.click();
    const afterFirstDisabled = button.disabled;
    button.click();
    return { beforeDisabled, afterFirstDisabled, afterSecondDisabled: button.disabled };
  });
  await seenPaymentRequestPromise;

  expect(paymentClickState.beforeDisabled).toBe(false);
  expect(paymentClickState.afterFirstDisabled).toBe(true);
  expect(paymentClickState.afterSecondDisabled).toBe(true);
  await expect(recordButton).toBeDisabled({ timeout: 10_000 });
  await expect(recordButton).toHaveText("Recording...");
  await page.waitForTimeout(250);
  expect(paymentRequestCount).toBe(1);
  releasePaymentRequest();
  const paymentResponse = await paymentResponsePromise;
  expect(paymentResponse.ok()).toBeTruthy();
  const payment = (await paymentResponse.json()) as { id: number };
  await page.unroute(paymentRoutePattern);

  const paymentStatus = page.getByTestId("invoice-payment-status");
  await expect(paymentStatus).toHaveText("Paid", { timeout: 15_000 });
  await expect(recordButton).toBeDisabled();

  const receiptButton = page.getByTestId("download-latest-receipt");
  await expect(receiptButton).toBeVisible({ timeout: 15_000 });

  const expectedFilename = `receipt-${invoice.id}-${payment.id}.pdf`;
  const routePattern = new RegExp(`/api/payments/${payment.id}/receipt\\.pdf$`);

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
  const clickState = await page.evaluate(() => {
    const button = document.querySelector('[data-testid="download-latest-receipt"]');
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Latest receipt button not found");
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
  await expect(receiptButton).toBeDisabled();
  await expect(receiptButton).toHaveText("Downloading...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseResponse();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(expectedFilename);

  await expect(receiptButton).toBeEnabled({ timeout: 15_000 });
  await expect(receiptButton).toHaveText("Download receipt");
  await page.unroute(routePattern);
});

test("recording a partial payment shows part-paid status and keeps payment action available", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Billing",
    last_name: `Part Paid ${Date.now()}`,
  });
  const invoice = await createInvoice(request, patientId);
  await addInvoiceLine(request, invoice.id, {
    description: "Partial payment proof",
    quantity: 1,
    unit_price_pence: 5000,
  });
  const issued = await issueInvoice(request, invoice.id);

  await primePageAuth(page, request);
  await page.goto(`${getBaseUrl()}/patients/${patientId}`, { waitUntil: "domcontentloaded" });

  await page.getByTestId("patient-tab-Financial").click();

  const invoiceRow = page.locator("tr", { hasText: issued.invoice_number });
  await expect(invoiceRow).toBeVisible({ timeout: 15_000 });
  await invoiceRow.getByRole("button", { name: "View" }).click();

  const recordButton = page.getByTestId("record-payment");
  await expect(recordButton).toBeVisible({ timeout: 15_000 });
  await expect(recordButton).toBeEnabled();
  await page.getByTestId("payment-amount").fill("25.00");

  const paymentResponsePromise = page.waitForResponse((response) => {
    return (
      response.request().method() === "POST" &&
      response.url().endsWith(`/api/invoices/${invoice.id}/payments`)
    );
  });
  await recordButton.click();

  const paymentResponse = await paymentResponsePromise;
  expect(paymentResponse.ok()).toBeTruthy();

  const paymentStatus = page.getByTestId("invoice-payment-status");
  await expect(paymentStatus).toHaveText("Part-paid", { timeout: 15_000 });
  await expect(recordButton).toBeEnabled();
  await expect(recordButton).toHaveText("Record payment");
  await expect(page.getByTestId("download-latest-receipt")).toBeVisible({ timeout: 15_000 });
});

test("finance summary receipt quick action honors backend filename", async ({ page, request }) => {
  const patientId = await createPatient(request, {
    first_name: "Finance",
    last_name: `Summary ${Date.now()}`,
  });
  const invoice = await createInvoice(request, patientId);
  await addInvoiceLine(request, invoice.id, {
    description: "Finance summary receipt proof",
    quantity: 1,
    unit_price_pence: 2500,
  });
  await issueInvoice(request, invoice.id);

  const token = await ensureAuthReady(request);
  const paymentResponse = await request.post(`${getBaseUrl()}/api/invoices/${invoice.id}/payments`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      amount_pence: 2500,
      method: "card",
    },
  });
  expect(paymentResponse.ok()).toBeTruthy();
  const payment = (await paymentResponse.json()) as { id: number };

  await primePageAuth(page, request);
  await page.goto(`${getBaseUrl()}/patients/${patientId}`, { waitUntil: "domcontentloaded" });

  const summaryReceiptButton = page.getByTestId(`finance-summary-receipt-${payment.id}`);
  await expect(summaryReceiptButton).toBeVisible({ timeout: 15_000 });

  const expectedFilename = `receipt-${invoice.id}-${payment.id}.pdf`;
  const routePattern = new RegExp(`/api/payments/${payment.id}/receipt\\.pdf$`);

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
  await summaryReceiptButton.click();
  await seenRequestPromise;

  await expect(summaryReceiptButton).toBeDisabled();
  await expect(summaryReceiptButton).toHaveText("Downloading...");

  releaseResponse();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(expectedFilename);

  await expect(summaryReceiptButton).toBeEnabled({ timeout: 15_000 });
  await expect(summaryReceiptButton).toHaveText("Receipt PDF");
  await page.unroute(routePattern);
});

test("selected invoice payment-row receipt honors backend filename", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Billing",
    last_name: `Payment Row ${Date.now()}`,
  });
  const invoice = await createInvoice(request, patientId);
  await addInvoiceLine(request, invoice.id, {
    description: "Payment row receipt proof",
    quantity: 1,
    unit_price_pence: 2500,
  });
  const issued = await issueInvoice(request, invoice.id);

  await primePageAuth(page, request);
  await page.goto(`${getBaseUrl()}/patients/${patientId}`, { waitUntil: "domcontentloaded" });

  await page.getByTestId("patient-tab-Financial").click();

  const invoiceRow = page.locator("tr", { hasText: issued.invoice_number });
  await expect(invoiceRow).toBeVisible({ timeout: 15_000 });
  await invoiceRow.getByRole("button", { name: "View" }).click();

  const recordButton = page.getByTestId("record-payment");
  await expect(recordButton).toBeVisible({ timeout: 15_000 });
  await page.getByTestId("payment-amount").fill("25.00");

  const paymentResponsePromise = page.waitForResponse((response) => {
    return (
      response.request().method() === "POST" &&
      response.url().endsWith(`/api/invoices/${invoice.id}/payments`)
    );
  });
  await recordButton.click();

  const paymentResponse = await paymentResponsePromise;
  expect(paymentResponse.ok()).toBeTruthy();
  const payment = (await paymentResponse.json()) as { id: number };

  const paymentStatus = page.getByTestId("invoice-payment-status");
  await expect(paymentStatus).toHaveText("Paid", { timeout: 15_000 });

  const receiptButton = page.getByTestId(`invoice-payment-receipt-${payment.id}`);
  await expect(receiptButton).toBeVisible({ timeout: 15_000 });

  const expectedFilename = `receipt-${invoice.id}-${payment.id}.pdf`;
  const routePattern = new RegExp(`/api/payments/${payment.id}/receipt\\.pdf$`);

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
  await receiptButton.click();
  await seenRequestPromise;

  await expect(receiptButton).toBeDisabled();
  await expect(receiptButton).toHaveText("Downloading...");

  releaseResponse();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(expectedFilename);

  await expect(receiptButton).toBeEnabled({ timeout: 15_000 });
  await expect(receiptButton).toHaveText("Receipt");
  await page.unroute(routePattern);
});

test("selected invoice latest receipt falls back to backend-contract filename without header", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Billing",
    last_name: `Latest Receipt ${Date.now()}`,
  });
  const invoice = await createInvoice(request, patientId);
  await addInvoiceLine(request, invoice.id, {
    description: "Latest receipt fallback proof",
    quantity: 1,
    unit_price_pence: 2500,
  });
  const issued = await issueInvoice(request, invoice.id);

  await primePageAuth(page, request);
  await page.goto(`${getBaseUrl()}/patients/${patientId}`, { waitUntil: "domcontentloaded" });

  await page.getByTestId("patient-tab-Financial").click();

  const invoiceRow = page.locator("tr", { hasText: issued.invoice_number });
  await expect(invoiceRow).toBeVisible({ timeout: 15_000 });
  await invoiceRow.getByRole("button", { name: "View" }).click();

  const recordButton = page.getByTestId("record-payment");
  await expect(recordButton).toBeVisible({ timeout: 15_000 });
  await page.getByTestId("payment-amount").fill("25.00");

  const paymentResponsePromise = page.waitForResponse((response) => {
    return (
      response.request().method() === "POST" &&
      response.url().endsWith(`/api/invoices/${invoice.id}/payments`)
    );
  });
  await recordButton.click();

  const paymentResponse = await paymentResponsePromise;
  expect(paymentResponse.ok()).toBeTruthy();
  const payment = (await paymentResponse.json()) as { id: number };

  const paymentStatus = page.getByTestId("invoice-payment-status");
  await expect(paymentStatus).toHaveText("Paid", { timeout: 15_000 });

  const receiptButton = page.getByTestId("download-latest-receipt");
  await expect(receiptButton).toBeVisible({ timeout: 15_000 });

  const expectedFilename = `receipt-${invoice.id}-${payment.id}.pdf`;
  const routePattern = new RegExp(`/api/payments/${payment.id}/receipt\\.pdf$`);

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
  await receiptButton.click();
  await seenRequestPromise;

  await expect(receiptButton).toBeDisabled();
  await expect(receiptButton).toHaveText("Downloading...");

  releaseResponse();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(expectedFilename);

  await expect(receiptButton).toBeEnabled({ timeout: 15_000 });
  await expect(receiptButton).toHaveText("Download receipt");
  await page.unroute(routePattern);
});
