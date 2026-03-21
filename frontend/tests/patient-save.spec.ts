import { expect, test, type Page } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

async function waitForPatientPersonalTab(page: Page, patientId: string) {
  await expect(page).toHaveURL(new RegExp(`/patients/${patientId}(?:\\?|$)`));
  await expect(page.getByTestId("patient-tabs")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("patient-tab-Personal")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Loading patient…")).toHaveCount(0);
}

test("patient personal save shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `SAVE${unique}`,
  });
  const token = await primePageAuth(page, request);
  const updatedNotes = `Patient save proof ${unique}`;

  await page.goto(`${baseUrl}/patients/${patientId}`, {
    waitUntil: "domcontentloaded",
  });
  await waitForPatientPersonalTab(page, patientId);

  await page.getByTestId("patient-tab-Personal").click();
  await expect(page.getByTestId("patient-tab-Personal")).toHaveAttribute("aria-selected", "true");

  await page.getByText("Patient details", { exact: true }).click();
  const notesField = page.getByTestId("patient-notes-field");
  await expect(notesField).toBeVisible();
  await notesField.fill(updatedNotes);

  const saveButton = page.getByTestId("patient-save-changes");
  await expect(saveButton).toBeEnabled();

  let requestCount = 0;
  const patientRoutePattern = new RegExp(`/api/patients/${patientId}$`);
  let seenSaveRequest!: () => void;
  const seenSaveRequestPromise = new Promise<void>((resolve) => {
    seenSaveRequest = resolve;
  });
  let releaseSaveRequest!: () => void;
  const releaseSaveRequestPromise = new Promise<void>((resolve) => {
    releaseSaveRequest = resolve;
  });
  await page.route(patientRoutePattern, async (route) => {
    if (route.request().method() !== "PATCH") {
      await route.continue();
      return;
    }
    requestCount += 1;
    if (requestCount === 1) {
      seenSaveRequest();
      await releaseSaveRequestPromise;
    }
    await route.continue();
  });
  const saveResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      response.url().includes(`/api/patients/${patientId}`)
  );

  const clickState = await saveButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Save changes button not found");
    }
    const beforeDisabled = button.disabled;
    button.click();
    const afterFirstDisabled = button.disabled;
    button.click();
    return { beforeDisabled, afterFirstDisabled, afterSecondDisabled: button.disabled };
  });
  await seenSaveRequestPromise;

  expect(clickState.beforeDisabled).toBe(false);
  expect(clickState.afterFirstDisabled).toBe(true);
  expect(clickState.afterSecondDisabled).toBe(true);
  await expect(saveButton).toBeDisabled();
  await expect(saveButton).toHaveText("Saving...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseSaveRequest();

  const saveResponse = await saveResponsePromise;
  expect(saveResponse.ok()).toBeTruthy();
  expect(saveResponse.request().postDataJSON()).toMatchObject({
    notes: updatedNotes,
  });
  await page.unroute(patientRoutePattern);

  await expect(saveButton).toHaveText("Save changes", { timeout: 15_000 });
  await expect(saveButton).toBeEnabled();

  const verifyResponse = await request.get(`${baseUrl}/api/patients/${patientId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(verifyResponse.ok()).toBeTruthy();
  const savedPatient = (await verifyResponse.json()) as { notes: string | null };
  expect(savedPatient.notes).toBe(updatedNotes);
});

test("patient archive shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `ARCHIVE${unique}`,
  });
  const token = await primePageAuth(page, request);

  await page.goto(`${baseUrl}/patients/${patientId}`, {
    waitUntil: "domcontentloaded",
  });
  await waitForPatientPersonalTab(page, patientId);

  await page.getByTestId("patient-tab-Personal").click();
  await expect(page.getByTestId("patient-tab-Personal")).toHaveAttribute("aria-selected", "true");
  await page.getByText("Patient details", { exact: true }).click();
  await expect(page.getByTestId("patient-notes-field")).toBeVisible();

  const archiveButton = page.getByTestId("patient-archive-toggle");
  await expect(archiveButton).toBeVisible();
  await expect(archiveButton).toBeEnabled();

  let requestCount = 0;
  const archiveRoutePattern = new RegExp(`/api/patients/${patientId}/archive$`);
  let seenArchiveRequest!: () => void;
  const seenArchiveRequestPromise = new Promise<void>((resolve) => {
    seenArchiveRequest = resolve;
  });
  let releaseArchiveRequest!: () => void;
  const releaseArchiveRequestPromise = new Promise<void>((resolve) => {
    releaseArchiveRequest = resolve;
  });
  await page.route(archiveRoutePattern, async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    requestCount += 1;
    if (requestCount === 1) {
      seenArchiveRequest();
      await releaseArchiveRequestPromise;
    }
    await route.continue();
  });
  const archiveResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().includes(`/api/patients/${patientId}/archive`)
  );
  page.once("dialog", (dialog) => dialog.accept());

  const clickState = await archiveButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Archive patient button not found");
    }
    const beforeDisabled = button.disabled;
    button.click();
    const afterFirstDisabled = button.disabled;
    button.click();
    return { beforeDisabled, afterFirstDisabled, afterSecondDisabled: button.disabled };
  });
  await seenArchiveRequestPromise;

  expect(clickState.beforeDisabled).toBe(false);
  expect(clickState.afterFirstDisabled).toBe(true);
  expect(clickState.afterSecondDisabled).toBe(true);
  await expect(archiveButton).toBeDisabled();
  await expect(archiveButton).toHaveText("Archiving...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseArchiveRequest();

  const archiveResponse = await archiveResponsePromise;
  expect(archiveResponse.ok()).toBeTruthy();
  await page.unroute(archiveRoutePattern);

  await expect(archiveButton).toHaveText("Restore patient", { timeout: 15_000 });
  await expect(archiveButton).toBeEnabled();

  const verifyResponse = await request.get(`${baseUrl}/api/patients/${patientId}?include_deleted=1`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(verifyResponse.ok()).toBeTruthy();
  const archivedPatient = (await verifyResponse.json()) as { deleted_at: string | null };
  expect(archivedPatient.deleted_at).toBeTruthy();
});

test("patient ledger save shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `LEDGER${unique}`,
  });
  const token = await primePageAuth(page, request);
  const reference = `LEDGER-${unique}`;
  const note = `Patient ledger proof ${unique}`;

  await page.goto(`${baseUrl}/patients/${patientId}`, {
    waitUntil: "domcontentloaded",
  });
  await waitForPatientPersonalTab(page, patientId);
  await expect(page.getByTestId("patient-tab-Personal")).toHaveAttribute("aria-selected", "true");

  const addPaymentButton = page.getByRole("button", { name: "Add payment" }).first();
  await expect(addPaymentButton).toBeVisible();
  await addPaymentButton.click();

  await expect(page.getByRole("heading", { name: "Add payment" })).toBeVisible();
  await page.getByPlaceholder("0.00").fill("25.00");
  await page.getByPlaceholder("Optional reference").fill(reference);
  await page.getByPlaceholder("Optional note").fill(note);

  const saveButton = page.getByTestId("patient-ledger-save");
  await expect(saveButton).toBeEnabled();

  let requestCount = 0;
  const ledgerRoutePattern = new RegExp(`/api/patients/${patientId}/payments$`);
  let seenLedgerRequest!: () => void;
  const seenLedgerRequestPromise = new Promise<void>((resolve) => {
    seenLedgerRequest = resolve;
  });
  let releaseLedgerRequest!: () => void;
  const releaseLedgerRequestPromise = new Promise<void>((resolve) => {
    releaseLedgerRequest = resolve;
  });
  await page.route(ledgerRoutePattern, async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    requestCount += 1;
    if (requestCount === 1) {
      seenLedgerRequest();
      await releaseLedgerRequestPromise;
    }
    await route.continue();
  });
  const ledgerResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().includes(`/api/patients/${patientId}/payments`)
  );

  const clickState = await saveButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Save entry button not found");
    }
    const beforeDisabled = button.disabled;
    button.click();
    const afterFirstDisabled = button.disabled;
    button.click();
    return { beforeDisabled, afterFirstDisabled, afterSecondDisabled: button.disabled };
  });
  await seenLedgerRequestPromise;

  expect(clickState.beforeDisabled).toBe(false);
  expect(clickState.afterFirstDisabled).toBe(true);
  expect(clickState.afterSecondDisabled).toBe(true);
  await expect(saveButton).toBeDisabled();
  await expect(saveButton).toHaveText("Saving...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseLedgerRequest();

  const ledgerResponse = await ledgerResponsePromise;
  expect(ledgerResponse.ok()).toBeTruthy();
  expect(ledgerResponse.request().postDataJSON()).toMatchObject({
    amount_pence: 2500,
    method: "card",
    reference,
    note,
  });
  await page.unroute(ledgerRoutePattern);

  await expect(page.getByRole("heading", { name: "Add payment" })).toHaveCount(0, {
    timeout: 15_000,
  });

  const verifyResponse = await request.get(`${baseUrl}/api/patients/${patientId}/ledger?limit=200`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(verifyResponse.ok()).toBeTruthy();
  const ledgerEntries = (await verifyResponse.json()) as Array<{
    entry_type: string;
    amount_pence: number;
    reference: string | null;
    note: string | null;
    method?: string | null;
  }>;
  expect(
    ledgerEntries.some(
      (entry) =>
        entry.entry_type === "payment" &&
        entry.amount_pence === -2500 &&
        entry.reference === reference &&
        entry.note === note &&
        entry.method === "card"
    )
  ).toBeTruthy();
});

test("patient recall save shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `RECALL${unique}`,
  });
  const token = await primePageAuth(page, request);
  const dueDate = "2026-12-31";

  await page.goto(`${baseUrl}/patients/${patientId}`, {
    waitUntil: "domcontentloaded",
  });
  await waitForPatientPersonalTab(page, patientId);
  await expect(page.getByTestId("patient-tab-Personal")).toHaveAttribute("aria-selected", "true");

  await page.getByTestId("patient-recall-due-date").fill(dueDate);
  await page.getByTestId("patient-recall-status").selectOption("booked");

  const saveButton = page.getByTestId("patient-recall-save");
  await expect(saveButton).toBeEnabled();

  let requestCount = 0;
  const recallRoutePattern = new RegExp(`/api/patients/${patientId}/recall$`);
  let seenRecallRequest!: () => void;
  const seenRecallRequestPromise = new Promise<void>((resolve) => {
    seenRecallRequest = resolve;
  });
  let releaseRecallRequest!: () => void;
  const releaseRecallRequestPromise = new Promise<void>((resolve) => {
    releaseRecallRequest = resolve;
  });
  await page.route(recallRoutePattern, async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    requestCount += 1;
    if (requestCount === 1) {
      seenRecallRequest();
      await releaseRecallRequestPromise;
    }
    await route.continue();
  });
  const recallResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().includes(`/api/patients/${patientId}/recall`)
  );

  const clickState = await saveButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Save recall button not found");
    }
    const beforeDisabled = button.disabled;
    button.click();
    const afterFirstDisabled = button.disabled;
    button.click();
    return { beforeDisabled, afterFirstDisabled, afterSecondDisabled: button.disabled };
  });
  await seenRecallRequestPromise;

  expect(clickState.beforeDisabled).toBe(false);
  expect(clickState.afterFirstDisabled).toBe(true);
  expect(clickState.afterSecondDisabled).toBe(true);
  await expect(saveButton).toBeDisabled();
  await expect(saveButton).toHaveText("Saving...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseRecallRequest();

  const recallResponse = await recallResponsePromise;
  expect(recallResponse.ok()).toBeTruthy();
  expect(recallResponse.request().postDataJSON()).toMatchObject({
    interval_months: 6,
    due_date: dueDate,
    status: "booked",
  });
  await page.unroute(recallRoutePattern);

  await expect(saveButton).toHaveText("Save recall", { timeout: 15_000 });
  await expect(saveButton).toBeEnabled();

  const verifyResponse = await request.get(`${baseUrl}/api/patients/${patientId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(verifyResponse.ok()).toBeTruthy();
  const savedPatient = (await verifyResponse.json()) as {
    recall_interval_months: number | null;
    recall_due_date: string | null;
    recall_status: string | null;
  };
  expect(savedPatient.recall_interval_months).toBe(6);
  expect(savedPatient.recall_due_date?.slice(0, 10)).toBe(dueDate);
  expect(savedPatient.recall_status).toBe("booked");
});

test("patient recall entry add shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `RECALLENTRY${unique}`,
  });
  const token = await primePageAuth(page, request);
  const dueDate = "2026-11-30";
  const notes = `Recall entry proof ${unique}`;

  await page.goto(`${baseUrl}/patients/${patientId}`, {
    waitUntil: "domcontentloaded",
  });
  await waitForPatientPersonalTab(page, patientId);

  await page.getByTestId("patient-tab-Schemes").click();
  await expect(page.getByTestId("patient-tab-Schemes")).toHaveAttribute("aria-selected", "true");

  const openButton = page.getByTestId("patient-recall-entry-open");
  await expect(openButton).toBeVisible();
  await openButton.click();

  await expect(page.getByRole("heading", { name: "Add recall" })).toBeVisible();
  await page.getByTestId("patient-recall-entry-due-date").fill(dueDate);
  await page.getByPlaceholder("Optional notes for this recall").fill(notes);

  const saveButton = page.getByTestId("patient-recall-entry-save");
  await expect(saveButton).toBeEnabled();

  let requestCount = 0;
  const recallEntryRoutePattern = new RegExp(`/api/patients/${patientId}/recalls$`);
  let seenRecallEntryRequest!: () => void;
  const seenRecallEntryRequestPromise = new Promise<void>((resolve) => {
    seenRecallEntryRequest = resolve;
  });
  let releaseRecallEntryRequest!: () => void;
  const releaseRecallEntryRequestPromise = new Promise<void>((resolve) => {
    releaseRecallEntryRequest = resolve;
  });
  await page.route(recallEntryRoutePattern, async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    requestCount += 1;
    if (requestCount === 1) {
      seenRecallEntryRequest();
      await releaseRecallEntryRequestPromise;
    }
    await route.continue();
  });
  const recallEntryResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().includes(`/api/patients/${patientId}/recalls`)
  );

  const clickState = await saveButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Add recall button not found");
    }
    const beforeDisabled = button.disabled;
    button.click();
    const afterFirstDisabled = button.disabled;
    button.click();
    return { beforeDisabled, afterFirstDisabled, afterSecondDisabled: button.disabled };
  });
  await seenRecallEntryRequestPromise;

  expect(clickState.beforeDisabled).toBe(false);
  expect(clickState.afterFirstDisabled).toBe(true);
  expect(clickState.afterSecondDisabled).toBe(true);
  await expect(saveButton).toBeDisabled();
  await expect(saveButton).toHaveText("Saving...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseRecallEntryRequest();

  const recallEntryResponse = await recallEntryResponsePromise;
  expect(recallEntryResponse.ok()).toBeTruthy();
  expect(recallEntryResponse.request().postDataJSON()).toMatchObject({
    kind: "exam",
    due_date: dueDate,
    notes,
  });
  await page.unroute(recallEntryRoutePattern);

  await expect(openButton).toHaveText("Add recall", { timeout: 15_000 });

  const verifyResponse = await request.get(`${baseUrl}/api/patients/${patientId}/recalls`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(verifyResponse.ok()).toBeTruthy();
  const savedRecalls = (await verifyResponse.json()) as Array<{
    kind: string;
    due_date: string | null;
    notes: string | null;
  }>;
  expect(
    savedRecalls.some(
      (item) =>
        item.kind === "exam" &&
        item.due_date?.slice(0, 10) === dueDate &&
        item.notes === notes
    )
  ).toBeTruthy();
});
