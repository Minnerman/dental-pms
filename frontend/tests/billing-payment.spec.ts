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
  const paymentResponsePromise = page.waitForResponse((response) => {
    return (
      response.request().method() === "POST" &&
      response.url().endsWith(`/api/invoices/${invoice.id}/payments`)
    );
  });
  await recordButton.click();

  await expect(recordButton).toBeDisabled({ timeout: 10_000 });
  const paymentResponse = await paymentResponsePromise;
  expect(paymentResponse.ok()).toBeTruthy();
  const payment = (await paymentResponse.json()) as { id: number };

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
  await expect(receiptButton).toHaveText("Download receipt");
  await page.unroute(routePattern);
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
