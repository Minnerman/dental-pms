import { expect, test } from "@playwright/test";

import { addInvoiceLine, createInvoice, createPatient, issueInvoice } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

test("patient invoice PDF download shows in-flight state and honors header filename", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Invoice",
    last_name: "PdfHardening",
  });
  const invoice = (await createInvoice(request, patientId, {
    notes: "Invoice PDF hardening proof",
  })) as { id: number };
  await addInvoiceLine(request, invoice.id, {
    description: "Invoice PDF proof line",
    quantity: 1,
    unit_price_pence: 4200,
  });
  const issued = (await issueInvoice(request, invoice.id)) as {
    id: number;
    invoice_number: string;
  };

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${patientId}`, { waitUntil: "domcontentloaded" });

  await page.getByTestId("patient-tab-Financial").click();

  const invoiceRow = page.locator("tr", { hasText: issued.invoice_number });
  await expect(invoiceRow).toBeVisible({ timeout: 15_000 });
  await invoiceRow.getByRole("button", { name: "View" }).click();

  const downloadButton = page.getByTestId(`invoice-download-pdf-${issued.id}`);
  await expect(downloadButton).toBeVisible({ timeout: 15_000 });

  const expectedFilename = `${issued.invoice_number}-header-proof.pdf`;
  const routePattern = new RegExp(`/api/invoices/${issued.id}/pdf$`);

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
  const clickState = await page.evaluate((id) => {
    const button = document.querySelector(`[data-testid="invoice-download-pdf-${id}"]`);
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Invoice PDF download button not found");
    }
    const beforeDisabled = button.disabled;
    button.click();
    const afterFirstDisabled = button.disabled;
    button.click();
    return { beforeDisabled, afterFirstDisabled, afterSecondDisabled: button.disabled };
  }, issued.id);
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

test("patient home finance summary invoice PDF shows in-flight state and honors header filename", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Invoice",
    last_name: "FinanceSummary",
  });
  const invoice = (await createInvoice(request, patientId, {
    notes: "Finance summary invoice PDF proof",
  })) as { id: number };
  await addInvoiceLine(request, invoice.id, {
    description: "Finance summary invoice proof line",
    quantity: 1,
    unit_price_pence: 4300,
  });
  const issued = (await issueInvoice(request, invoice.id)) as {
    id: number;
    invoice_number: string;
  };

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${patientId}`, { waitUntil: "domcontentloaded" });

  const downloadButton = page.getByTestId(`finance-summary-invoice-${issued.id}`);
  await expect(downloadButton).toBeVisible({ timeout: 15_000 });

  const expectedFilename = `${issued.invoice_number}-finance-summary-proof.pdf`;
  const routePattern = new RegExp(`/api/invoices/${issued.id}/pdf$`);

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
  await downloadButton.click();
  await seenRequestPromise;

  await expect(downloadButton).toBeDisabled();
  await expect(downloadButton).toHaveText("Downloading PDF...");

  releaseResponse();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(expectedFilename);

  await expect(downloadButton).toBeEnabled({ timeout: 15_000 });
  await expect(downloadButton).toHaveText("Invoice PDF");
  await page.unroute(routePattern);
});
