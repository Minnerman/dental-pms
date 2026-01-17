import { expect, test } from "@playwright/test";

import { addInvoiceLine, createInvoice, createPatient, issueInvoice } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

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

  await page.getByRole("button", { name: /Invoices/ }).click();

  const invoiceRow = page.locator("tr", { hasText: issued.invoice_number });
  await expect(invoiceRow).toBeVisible({ timeout: 15_000 });
  await invoiceRow.getByRole("button", { name: "View" }).click();

  const recordButton = page.getByTestId("record-payment");
  await expect(recordButton).toBeVisible({ timeout: 15_000 });
  await expect(recordButton).toBeEnabled();

  await page.getByTestId("payment-amount").fill("25.00");
  await recordButton.click();

  await expect(recordButton).toBeDisabled({ timeout: 10_000 });

  const paymentStatus = page.getByTestId("invoice-payment-status");
  await expect(paymentStatus).toHaveText("Paid", { timeout: 15_000 });
  await expect(recordButton).toBeDisabled();

  const receiptButton = page.getByTestId("download-latest-receipt");
  await expect(receiptButton).toBeVisible({ timeout: 15_000 });
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    receiptButton.click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/receipt-/);
});
