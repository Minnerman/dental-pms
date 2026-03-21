import { expect, test, type Page } from "@playwright/test";

import { getBaseUrl, primePageAuth } from "./helpers/auth";
import { createPatient } from "./helpers/api";

async function waitForPatientClinicalPage(page: Page, patientId: string) {
  await expect(page).toHaveURL(new RegExp(`/patients/${patientId}/clinical`));
  await expect(page.getByTestId("patient-tabs")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("patient-tab-Notes")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Loading patient…")).toHaveCount(0);
}

test("patient notes tab allows selecting admin note type on create", async ({ page, request }) => {
  const unique = Date.now();
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `NOTE${unique}`,
  });
  const noteBody = `Patient admin note ${unique}`;

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${patientId}/clinical`, {
    waitUntil: "domcontentloaded",
  });
  await waitForPatientClinicalPage(page, patientId);

  await page.getByTestId("patient-tab-Notes").click();
  await expect(page.getByTestId("patient-tab-Notes")).toHaveAttribute("aria-selected", "true");

  await page.getByTestId("patient-note-type-select").selectOption("admin");
  await page.getByPlaceholder("Write a clinical or admin note...").fill(noteBody);
  const addNoteButton = page.getByTestId("patient-note-add");
  await expect(addNoteButton).toBeEnabled();

  let requestCount = 0;
  const noteRoutePattern = new RegExp(`/api/patients/${patientId}/notes$`);
  let seenCreateRequest!: () => void;
  const seenCreateRequestPromise = new Promise<void>((resolve) => {
    seenCreateRequest = resolve;
  });
  let releaseCreateRequest!: () => void;
  const releaseCreateRequestPromise = new Promise<void>((resolve) => {
    releaseCreateRequest = resolve;
  });
  await page.route(noteRoutePattern, async (route) => {
    requestCount += 1;
    if (requestCount === 1) {
      seenCreateRequest();
      await releaseCreateRequestPromise;
    }
    await route.continue();
  });
  const createResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().includes(`/api/patients/${patientId}/notes`)
  );

  const clickState = await addNoteButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Add note button not found");
    }
    const beforeDisabled = button.disabled;
    button.click();
    const afterFirstDisabled = button.disabled;
    button.click();
    return { beforeDisabled, afterFirstDisabled, afterSecondDisabled: button.disabled };
  });
  await seenCreateRequestPromise;

  expect(clickState.beforeDisabled).toBe(false);
  expect(clickState.afterFirstDisabled).toBe(true);
  expect(clickState.afterSecondDisabled).toBe(true);
  await expect(addNoteButton).toBeDisabled();
  await expect(addNoteButton).toHaveText("Saving...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseCreateRequest();

  const createResponse = await createResponsePromise;
  expect(createResponse.ok()).toBeTruthy();
  const createdNote = (await createResponse.json()) as { id: number };
  expect(createResponse.request().postDataJSON()).toMatchObject({
    body: noteBody,
    note_type: "admin",
  });
  await page.unroute(noteRoutePattern);

  const noteCard = page.getByText(noteBody, { exact: true }).locator("xpath=..");
  await expect(noteCard).toBeVisible({ timeout: 15_000 });
  await expect(noteCard.getByText("Admin", { exact: true })).toBeVisible({ timeout: 15_000 });

  await page.getByTestId(`patient-note-open-${createdNote.id}`).click();
  await expect(page).toHaveURL(new RegExp(`/notes\\?note=${createdNote.id}\\b`), {
    timeout: 15_000,
  });
  await expect(page.getByTestId("note-detail-type")).toHaveValue("admin");
  await expect(page.getByTestId("note-detail-body")).toHaveValue(noteBody);
});

test("patient clinical note entry shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `CLIN${unique}`,
  });
  const noteBody = `Clinical tooth note ${unique}`;

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${patientId}/clinical`, {
    waitUntil: "domcontentloaded",
  });
  await waitForPatientClinicalPage(page, patientId);
  await expect(page.getByTestId("patient-tab-Medical")).toHaveAttribute("aria-selected", "true");
  await page.getByRole("button", { name: /^Notes \(\d+\)$/ }).click();
  await expect(page.getByText("Add clinical note", { exact: true })).toBeVisible({
    timeout: 15_000,
  });

  await page.getByTestId("patient-clinical-note-tooth").selectOption("UR6");
  await page.getByTestId("patient-clinical-note-body").fill(noteBody);
  const addNoteButton = page.getByTestId("patient-clinical-note-add");
  await expect(addNoteButton).toBeEnabled();

  let requestCount = 0;
  const noteRoutePattern = new RegExp(`/api/patients/${patientId}/tooth-notes$`);
  let seenCreateRequest!: () => void;
  const seenCreateRequestPromise = new Promise<void>((resolve) => {
    seenCreateRequest = resolve;
  });
  let releaseCreateRequest!: () => void;
  const releaseCreateRequestPromise = new Promise<void>((resolve) => {
    releaseCreateRequest = resolve;
  });
  await page.route(noteRoutePattern, async (route) => {
    requestCount += 1;
    if (requestCount === 1) {
      seenCreateRequest();
      await releaseCreateRequestPromise;
    }
    await route.continue();
  });
  const createResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().includes(`/api/patients/${patientId}/tooth-notes`)
  );

  const clickState = await addNoteButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Clinical Add note button not found");
    }
    const beforeDisabled = button.disabled;
    button.click();
    const afterFirstDisabled = button.disabled;
    button.click();
    return { beforeDisabled, afterFirstDisabled, afterSecondDisabled: button.disabled };
  });
  await seenCreateRequestPromise;

  expect(clickState.beforeDisabled).toBe(false);
  expect(clickState.afterFirstDisabled).toBe(true);
  expect(clickState.afterSecondDisabled).toBe(true);
  await expect(addNoteButton).toBeDisabled();
  await expect(addNoteButton).toHaveText("Saving...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseCreateRequest();

  const createResponse = await createResponsePromise;
  expect(createResponse.ok()).toBeTruthy();
  expect(createResponse.request().postDataJSON()).toMatchObject({
    tooth: "UR6",
    surface: null,
    note: noteBody,
  });
  await page.unroute(noteRoutePattern);

  await expect(page.getByText("Note saved.", { exact: true })).toBeVisible({ timeout: 15_000 });
  const savedNoteCard = page
    .getByText(noteBody, { exact: true })
    .locator("xpath=ancestor::div[contains(@class, 'card')][1]");
  await expect(savedNoteCard).toBeVisible({ timeout: 15_000 });
  await expect(savedNoteCard).toContainText("UR6");
  await expect(savedNoteCard).toContainText("Tooth note");
  await expect(page.getByTestId("patient-clinical-note-body")).toHaveValue("");
  await expect(addNoteButton).toHaveText("Add note");
});

test("patient chart tooth note add shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `CHARTNOTE${unique}`,
  });
  const token = await primePageAuth(page, request);
  const noteBody = `Chart tooth note ${unique}`;

  await page.goto(`${baseUrl}/patients/${patientId}/clinical`, {
    waitUntil: "domcontentloaded",
  });
  await waitForPatientClinicalPage(page, patientId);
  await expect(page.getByTestId("patient-tab-Medical")).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText("Add tooth note", { exact: true })).toBeVisible();

  await page.getByTestId("tooth-button-UR6").click();
  await page.getByTestId("patient-chart-note-surface").fill("O");
  await page.getByTestId("patient-chart-note-body").fill(noteBody);

  const addNoteButton = page.getByTestId("patient-chart-note-add");
  await expect(addNoteButton).toBeEnabled();

  let requestCount = 0;
  const noteRoutePattern = new RegExp(`/api/patients/${patientId}/tooth-notes$`);
  let seenCreateRequest!: () => void;
  const seenCreateRequestPromise = new Promise<void>((resolve) => {
    seenCreateRequest = resolve;
  });
  let releaseCreateRequest!: () => void;
  const releaseCreateRequestPromise = new Promise<void>((resolve) => {
    releaseCreateRequest = resolve;
  });
  await page.route(noteRoutePattern, async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    requestCount += 1;
    if (requestCount === 1) {
      seenCreateRequest();
      await releaseCreateRequestPromise;
    }
    await route.continue();
  });
  const createResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().includes(`/api/patients/${patientId}/tooth-notes`)
  );

  const clickState = await addNoteButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Chart Add note button not found");
    }
    const beforeDisabled = button.disabled;
    button.click();
    const afterFirstDisabled = button.disabled;
    button.click();
    return { beforeDisabled, afterFirstDisabled, afterSecondDisabled: button.disabled };
  });
  await seenCreateRequestPromise;

  expect(clickState.beforeDisabled).toBe(false);
  expect(clickState.afterFirstDisabled).toBe(true);
  expect(clickState.afterSecondDisabled).toBe(true);
  await expect(addNoteButton).toBeDisabled();
  await expect(addNoteButton).toHaveText("Saving...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseCreateRequest();

  const createResponse = await createResponsePromise;
  expect(createResponse.ok()).toBeTruthy();
  expect(createResponse.request().postDataJSON()).toMatchObject({
    tooth: "UR6",
    surface: "O",
    note: noteBody,
  });
  await page.unroute(noteRoutePattern);

  await expect(page.getByText("Note saved.", { exact: true })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("patient-chart-note-body")).toHaveValue("");
  await expect(addNoteButton).toHaveText("Add note");

  const verifyResponse = await request.get(
    `${baseUrl}/api/patients/${patientId}/tooth-history?tooth=UR6`,
    {
      headers: { Authorization: `Bearer ${token}` },
    }
  );
  expect(verifyResponse.ok()).toBeTruthy();
  const toothHistory = (await verifyResponse.json()) as {
    notes?: Array<{ tooth?: string | null; surface?: string | null; note?: string | null }>;
  };
  expect(
    (toothHistory.notes ?? []).some(
      (entry) => entry.tooth === "UR6" && entry.surface === "O" && entry.note === noteBody
    )
  ).toBeTruthy();
});

test("patient treatment plan add shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `PLAN${unique}`,
  });
  const token = await primePageAuth(page, request);
  const planCode = "PLAN";
  const planDescription = `Planned treatment ${unique}`;

  await page.goto(`${baseUrl}/patients/${patientId}/clinical`, {
    waitUntil: "domcontentloaded",
  });
  await waitForPatientClinicalPage(page, patientId);

  await page.getByRole("button", { name: /^Treatment plan \(\d+\)$/ }).click();
  await expect(page.getByRole("button", { name: /^Treatment plan \(\d+\)$/ })).toHaveClass(
    /active/
  );

  const openButton = page.getByTestId("patient-treatment-plan-open");
  await expect(openButton).toBeVisible();
  await openButton.click();

  await expect(page.getByRole("heading", { name: "Add treatment plan item" })).toBeVisible();
  await page.getByTestId("patient-treatment-plan-code").fill(planCode);
  await page.getByTestId("patient-treatment-plan-description").fill(planDescription);

  const addItemButton = page.getByTestId("patient-treatment-plan-add");
  await expect(addItemButton).toBeEnabled();

  let requestCount = 0;
  const planRoutePattern = new RegExp(`/api/patients/${patientId}/treatment-plan$`);
  let seenCreateRequest!: () => void;
  const seenCreateRequestPromise = new Promise<void>((resolve) => {
    seenCreateRequest = resolve;
  });
  let releaseCreateRequest!: () => void;
  const releaseCreateRequestPromise = new Promise<void>((resolve) => {
    releaseCreateRequest = resolve;
  });
  await page.route(planRoutePattern, async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    requestCount += 1;
    if (requestCount === 1) {
      seenCreateRequest();
      await releaseCreateRequestPromise;
    }
    await route.continue();
  });
  const createResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().includes(`/api/patients/${patientId}/treatment-plan`)
  );

  const clickState = await addItemButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Add item button not found");
    }
    const beforeDisabled = button.disabled;
    button.click();
    const afterFirstDisabled = button.disabled;
    button.click();
    return { beforeDisabled, afterFirstDisabled, afterSecondDisabled: button.disabled };
  });
  await seenCreateRequestPromise;

  expect(clickState.beforeDisabled).toBe(false);
  expect(clickState.afterFirstDisabled).toBe(true);
  expect(clickState.afterSecondDisabled).toBe(true);
  await expect(addItemButton).toBeDisabled();
  await expect(addItemButton).toHaveText("Saving...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseCreateRequest();

  const createResponse = await createResponsePromise;
  expect(createResponse.ok()).toBeTruthy();
  expect(createResponse.request().postDataJSON()).toMatchObject({
    procedure_code: planCode,
    description: planDescription,
  });
  await page.unroute(planRoutePattern);

  await expect(page.getByRole("heading", { name: "Add treatment plan item" })).toHaveCount(0, {
    timeout: 15_000,
  });
  await expect(page.getByText(planDescription, { exact: true })).toBeVisible({ timeout: 15_000 });

  const verifyResponse = await request.get(
    `${baseUrl}/api/patients/${patientId}/clinical/summary?limit=200`,
    {
      headers: { Authorization: `Bearer ${token}` },
    }
  );
  expect(verifyResponse.ok()).toBeTruthy();
  const clinicalSummary = (await verifyResponse.json()) as {
    treatment_plan_items?: Array<{ procedure_code?: string | null; description?: string | null }>;
  };
  expect(
    (clinicalSummary.treatment_plan_items ?? []).some(
      (item) => item.procedure_code === planCode && item.description === planDescription
    )
  ).toBeTruthy();
});

test("patient BPE save shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `BPE${unique}`,
  });
  const token = await primePageAuth(page, request);
  const scores = ["0", "1", "2", "3", "*", "4"];

  await page.goto(`${baseUrl}/patients/${patientId}/clinical`, {
    waitUntil: "domcontentloaded",
  });
  await waitForPatientClinicalPage(page, patientId);
  await expect(page.getByTestId("patient-tab-Medical")).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("button", { name: "Save BPE" })).toBeVisible();

  const sextants = ["UR", "UA", "UL", "LL", "LA", "LR"] as const;
  for (const [index, sextant] of sextants.entries()) {
    await page.getByTestId(`patient-bpe-score-${sextant}`).fill(scores[index]);
  }

  const saveButton = page.getByTestId("patient-bpe-save");
  await expect(saveButton).toBeEnabled();

  let requestCount = 0;
  const bpeRoutePattern = new RegExp(`/api/patients/${patientId}/clinical/bpe$`);
  let seenSaveRequest!: () => void;
  const seenSaveRequestPromise = new Promise<void>((resolve) => {
    seenSaveRequest = resolve;
  });
  let releaseSaveRequest!: () => void;
  const releaseSaveRequestPromise = new Promise<void>((resolve) => {
    releaseSaveRequest = resolve;
  });
  await page.route(bpeRoutePattern, async (route) => {
    if (route.request().method() !== "POST") {
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
      response.request().method() === "POST" &&
      response.url().includes(`/api/patients/${patientId}/clinical/bpe`)
  );

  const clickState = await saveButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Save BPE button not found");
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
    scores,
  });
  await page.unroute(bpeRoutePattern);

  await expect(page.getByText("BPE saved.", { exact: true })).toBeVisible({ timeout: 15_000 });
  await expect(saveButton).toHaveText("Save BPE", { timeout: 15_000 });

  const verifyResponse = await request.get(
    `${baseUrl}/api/patients/${patientId}/clinical/summary`,
    {
      headers: { Authorization: `Bearer ${token}` },
    }
  );
  expect(verifyResponse.ok()).toBeTruthy();
  const clinicalSummary = (await verifyResponse.json()) as {
    bpe_scores?: string[] | null;
    bpe_recorded_at?: string | null;
  };
  expect(clinicalSummary.bpe_scores).toEqual(scores);
  expect(clinicalSummary.bpe_recorded_at).toBeTruthy();
});

test("notes detail save shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `NOTEEDIT${unique}`,
  });
  const noteBody = `Patient note edit seed ${unique}`;
  const editedBody = `Patient note edit updated ${unique}`;

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${patientId}/clinical`, {
    waitUntil: "domcontentloaded",
  });
  await waitForPatientClinicalPage(page, patientId);

  await page.getByTestId("patient-tab-Notes").click();
  await expect(page.getByTestId("patient-tab-Notes")).toHaveAttribute("aria-selected", "true");

  await page.getByTestId("patient-note-type-select").selectOption("admin");
  await page.getByPlaceholder("Write a clinical or admin note...").fill(noteBody);
  const addNoteButton = page.getByTestId("patient-note-add");
  await expect(addNoteButton).toBeEnabled();
  await addNoteButton.click();

  const noteCard = page.getByText(noteBody, { exact: true }).locator("xpath=..");
  await expect(noteCard).toBeVisible({ timeout: 15_000 });
  await expect(noteCard.getByText("Admin", { exact: true })).toBeVisible({ timeout: 15_000 });

  const openButton = noteCard.locator('[data-testid^="patient-note-open-"]');
  await openButton.click();
  await expect(page).toHaveURL(/\/notes\?note=\d+\b/, { timeout: 15_000 });

  const noteIdMatch = page.url().match(/note=(\d+)/);
  expect(noteIdMatch).toBeTruthy();
  const noteId = Number(noteIdMatch?.[1]);

  await expect(page.getByTestId("note-detail-type")).toHaveValue("admin");
  await expect(page.getByTestId("note-detail-body")).toHaveValue(noteBody);
  await page.getByTestId("note-detail-body").fill(editedBody);

  const saveButton = page.getByTestId("note-detail-save");
  await expect(saveButton).toBeEnabled();

  let requestCount = 0;
  const saveRoutePattern = new RegExp(`/api/notes/${noteId}$`);
  let seenSaveRequest!: () => void;
  const seenSaveRequestPromise = new Promise<void>((resolve) => {
    seenSaveRequest = resolve;
  });
  let releaseSaveRequest!: () => void;
  const releaseSaveRequestPromise = new Promise<void>((resolve) => {
    releaseSaveRequest = resolve;
  });
  await page.route(saveRoutePattern, async (route) => {
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
      response.url().includes(`/api/notes/${noteId}`)
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
    body: editedBody,
    note_type: "admin",
  });
  await page.unroute(saveRoutePattern);

  await expect(page.getByText("Note updated.", { exact: true })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("note-detail-body")).toHaveValue(editedBody);
  await expect(saveButton).toHaveText("Save changes");
});

test("notes detail archive shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `NOTEARCH${unique}`,
  });
  const noteBody = `Patient note archive seed ${unique}`;

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${patientId}/clinical`, {
    waitUntil: "domcontentloaded",
  });
  await waitForPatientClinicalPage(page, patientId);

  await page.getByTestId("patient-tab-Notes").click();
  await expect(page.getByTestId("patient-tab-Notes")).toHaveAttribute("aria-selected", "true");

  await page.getByTestId("patient-note-type-select").selectOption("admin");
  await page.getByPlaceholder("Write a clinical or admin note...").fill(noteBody);
  const addNoteButton = page.getByTestId("patient-note-add");
  await expect(addNoteButton).toBeEnabled();
  await addNoteButton.click();

  const noteCard = page.getByText(noteBody, { exact: true }).locator("xpath=..");
  await expect(noteCard).toBeVisible({ timeout: 15_000 });
  await expect(noteCard.getByText("Admin", { exact: true })).toBeVisible({ timeout: 15_000 });

  const openButton = noteCard.locator('[data-testid^="patient-note-open-"]');
  await openButton.click();
  await expect(page).toHaveURL(/\/notes\?note=\d+\b/, { timeout: 15_000 });

  const noteIdMatch = page.url().match(/note=(\d+)/);
  expect(noteIdMatch).toBeTruthy();
  const noteId = Number(noteIdMatch?.[1]);

  const showArchivedToggle = page.getByLabel("Show archived");
  await showArchivedToggle.check();
  await expect(showArchivedToggle).toBeChecked();

  const archiveButton = page.getByTestId("note-detail-archive");
  await expect(archiveButton).toBeEnabled();

  let requestCount = 0;
  const archiveRoutePattern = new RegExp(`/api/notes/${noteId}/archive$`);
  let seenArchiveRequest!: () => void;
  const seenArchiveRequestPromise = new Promise<void>((resolve) => {
    seenArchiveRequest = resolve;
  });
  let releaseArchiveRequest!: () => void;
  const releaseArchiveRequestPromise = new Promise<void>((resolve) => {
    releaseArchiveRequest = resolve;
  });
  await page.route(archiveRoutePattern, async (route) => {
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
      response.url().includes(`/api/notes/${noteId}/archive`)
  );
  page.once("dialog", (dialog) => dialog.accept());

  const clickState = await archiveButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Archive button not found");
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

  await expect(page.getByText("Note archived.", { exact: true })).toBeVisible({ timeout: 15_000 });
  await expect(archiveButton).toHaveText("Restore");
  await expect(archiveButton).toBeEnabled({ timeout: 15_000 });
});
