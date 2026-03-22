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

test("patient invoice issue shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Invoice",
    last_name: `IssueHardening${unique}`,
  });
  const token = await primePageAuth(page, request);
  const invoice = (await createInvoice(request, patientId, {
    notes: `Invoice issue proof ${unique}`,
  })) as { id: number; invoice_number: string };
  await addInvoiceLine(request, invoice.id, {
    description: `Invoice issue line ${unique}`,
    quantity: 1,
    unit_price_pence: 5200,
  });

  await page.goto(`${baseUrl}/patients/${patientId}`, { waitUntil: "domcontentloaded" });
  await page.getByTestId("patient-tab-Financial").click();

  const invoiceRow = page.locator("tr", { hasText: invoice.invoice_number });
  await expect(invoiceRow).toBeVisible({ timeout: 15_000 });
  await invoiceRow.getByRole("button", { name: "View" }).click();

  const issueButton = page.getByTestId(`invoice-issue-${invoice.id}`);
  await expect(issueButton).toBeEnabled({ timeout: 15_000 });

  let requestCount = 0;
  const routePattern = new RegExp(`/api/invoices/${invoice.id}/issue$`);
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
  const issueResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith(`/api/invoices/${invoice.id}/issue`)
  );

  const clickState = await issueButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Issue invoice button not found");
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
  await expect(issueButton).toBeDisabled();
  await expect(issueButton).toHaveText("Issuing...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseResponse();

  const issueResponse = await issueResponsePromise;
  expect(issueResponse.ok()).toBeTruthy();
  await page.unroute(routePattern);

  await expect(issueButton).toHaveCount(0, { timeout: 15_000 });
  await expect(page.getByText(/Status:\s*issued/i)).toBeVisible({ timeout: 15_000 });

  const verifyResponse = await request.get(`${baseUrl}/api/invoices/${invoice.id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(verifyResponse.ok()).toBeTruthy();
  const updatedInvoice = (await verifyResponse.json()) as { status: string };
  expect(updatedInvoice.status).toBe("issued");
});

test("patient invoice create shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Invoice",
    last_name: `CreateHardening${unique}`,
  });
  const token = await primePageAuth(page, request);
  const notes = `Invoice create proof ${unique}`;
  const discount = "1.50";

  await page.goto(`${baseUrl}/patients/${patientId}`, { waitUntil: "domcontentloaded" });
  await page.getByTestId("patient-tab-Financial").click();

  await page.getByTestId("patient-invoice-notes").fill(notes);
  await page.getByTestId("patient-invoice-discount").fill(discount);

  const createButton = page.getByTestId("patient-invoice-create");
  await expect(createButton).toBeEnabled();

  let requestCount = 0;
  const routePattern = /\/api\/invoices$/;
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
  const invoiceResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" && response.url().endsWith("/api/invoices")
  );

  const clickState = await createButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Create invoice button not found");
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

  const invoiceResponse = await invoiceResponsePromise;
  expect(invoiceResponse.ok()).toBeTruthy();
  expect(invoiceResponse.request().postDataJSON()).toMatchObject({
    patient_id: Number(patientId),
    notes,
    discount_pence: 150,
  });
  const createdInvoice = (await invoiceResponse.json()) as {
    id: number;
    notes?: string | null;
    discount_pence: number;
  };
  expect(createdInvoice.notes).toBe(notes);
  expect(createdInvoice.discount_pence).toBe(150);
  await page.unroute(routePattern);

  await expect(createButton).toHaveText("New invoice", { timeout: 15_000 });
  await expect(createButton).toBeEnabled();

  const verifyResponse = await request.get(`${baseUrl}/api/invoices/${createdInvoice.id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(verifyResponse.ok()).toBeTruthy();
  const persistedInvoice = (await verifyResponse.json()) as {
    notes?: string | null;
    discount_pence: number;
  };
  expect(persistedInvoice.notes).toBe(notes);
  expect(persistedInvoice.discount_pence).toBe(150);
});

test("patient invoice save shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Invoice",
    last_name: `SaveHardening${unique}`,
  });
  const token = await primePageAuth(page, request);
  const invoice = (await createInvoice(request, patientId, {
    notes: `Invoice seed ${unique}`,
    discount_pence: 50,
  })) as { id: number; invoice_number: string };
  const updatedNotes = `Invoice save proof ${unique}`;
  const updatedDiscount = "2.25";

  await page.goto(`${baseUrl}/patients/${patientId}`, { waitUntil: "domcontentloaded" });
  await page.getByTestId("patient-tab-Financial").click();

  const invoiceRow = page.locator("tr", { hasText: invoice.invoice_number });
  await expect(invoiceRow).toBeVisible({ timeout: 15_000 });
  await invoiceRow.getByRole("button", { name: "View" }).click();

  await page.getByTestId("patient-invoice-edit-notes").fill(updatedNotes);
  await page.getByTestId("patient-invoice-edit-discount").fill(updatedDiscount);

  const saveButton = page.getByTestId("patient-invoice-save");
  await expect(saveButton).toBeEnabled({ timeout: 15_000 });

  let requestCount = 0;
  const routePattern = new RegExp(`/api/invoices/${invoice.id}$`);
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
  const saveResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      response.url().endsWith(`/api/invoices/${invoice.id}`)
  );

  const clickState = await saveButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Save invoice button not found");
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
  await expect(saveButton).toBeDisabled();
  await expect(saveButton).toHaveText("Saving...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseResponse();

  const saveResponse = await saveResponsePromise;
  expect(saveResponse.ok()).toBeTruthy();
  expect(saveResponse.request().postDataJSON()).toMatchObject({
    notes: updatedNotes,
    discount_pence: 225,
  });
  await page.unroute(routePattern);

  await expect(saveButton).toHaveText("Save invoice", { timeout: 15_000 });
  await expect(saveButton).toBeEnabled();

  const verifyResponse = await request.get(`${baseUrl}/api/invoices/${invoice.id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(verifyResponse.ok()).toBeTruthy();
  const updatedInvoice = (await verifyResponse.json()) as {
    notes?: string | null;
    discount_pence: number;
  };
  expect(updatedInvoice.notes).toBe(updatedNotes);
  expect(updatedInvoice.discount_pence).toBe(225);
});

test("patient invoice void shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Invoice",
    last_name: `VoidHardening${unique}`,
  });
  const token = await primePageAuth(page, request);
  const invoice = (await createInvoice(request, patientId, {
    notes: `Invoice void proof ${unique}`,
  })) as { id: number; invoice_number: string };
  await addInvoiceLine(request, invoice.id, {
    description: `Invoice void line ${unique}`,
    quantity: 1,
    unit_price_pence: 4100,
  });

  await page.goto(`${baseUrl}/patients/${patientId}`, { waitUntil: "domcontentloaded" });
  await page.getByTestId("patient-tab-Financial").click();

  const invoiceRow = page.locator("tr", { hasText: invoice.invoice_number });
  await expect(invoiceRow).toBeVisible({ timeout: 15_000 });
  await invoiceRow.getByRole("button", { name: "View" }).click();

  const voidButton = page.getByTestId(`invoice-void-${invoice.id}`);
  await expect(voidButton).toBeEnabled({ timeout: 15_000 });

  let requestCount = 0;
  const routePattern = new RegExp(`/api/invoices/${invoice.id}/void$`);
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
  const voidResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith(`/api/invoices/${invoice.id}/void`)
  );
  page.once("dialog", (dialog) => dialog.accept());

  const clickState = await voidButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Void invoice button not found");
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
  await expect(voidButton).toBeDisabled();
  await expect(voidButton).toHaveText("Voiding...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseResponse();

  const voidResponse = await voidResponsePromise;
  expect(voidResponse.ok()).toBeTruthy();
  await page.unroute(routePattern);

  await expect(voidButton).toHaveCount(0, { timeout: 15_000 });
  await expect(page.getByText(/Status:\s*void/i)).toBeVisible({ timeout: 15_000 });

  const verifyResponse = await request.get(`${baseUrl}/api/invoices/${invoice.id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(verifyResponse.ok()).toBeTruthy();
  const updatedInvoice = (await verifyResponse.json()) as { status: string };
  expect(updatedInvoice.status).toBe("void");
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
