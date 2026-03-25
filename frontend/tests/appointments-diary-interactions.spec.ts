import fs from "node:fs/promises";
import path from "node:path";

import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import { createAppointment, createAppointmentNote, createPatient } from "./helpers/api";
import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

const stage158bDir = path.resolve(__dirname, "..", "..", ".run", "stage158b");
const stage158dDir = path.resolve(__dirname, "..", "..", ".run", "stage158d");

type AppointmentDetails = {
  id: number;
  status: string;
  starts_at: string;
  ends_at: string;
  location?: string | null;
  location_type: "clinic" | "visit";
};

async function getAppointmentById(
  request: APIRequestContext,
  appointmentId: number
): Promise<AppointmentDetails> {
  const token = await ensureAuthReady(request);
  const baseUrl = getBaseUrl();
  const response = await request.get(`${baseUrl}/api/appointments/${appointmentId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as AppointmentDetails;
}

async function waitForDiaryPage(page: Page) {
  await expect(page.getByTestId("appointments-page")).toBeVisible({ timeout: 20_000 });
  await expect(page).not.toHaveURL(/\/login|\/change-password/);
}

async function switchToDayView(page: Page) {
  const explicit = page.getByTestId("appointments-calendar-view-day");
  if (await explicit.count()) {
    await explicit.click();
    return;
  }
  const fallback = page
    .locator(".rbc-toolbar button")
    .filter({ hasText: /^day$/i })
    .first();
  await expect(fallback).toBeVisible({ timeout: 10_000 });
  await fallback.click();
}

async function firstDiaryEvent(page: Page) {
  await page.evaluate(() => {
    const scroller = document.querySelector(".rbc-time-content") as HTMLElement | null;
    if (scroller) scroller.scrollTop = 0;
  });
  const events = page.locator('[data-testid^="appointment-event-"]');
  await expect(events.first()).toBeVisible({ timeout: 15_000 });
  return events.first();
}

function daySheetRow(page: Page, patientMarker: string) {
  return page
    .locator(".day-sheet-table tbody tr")
    .filter({ hasText: patientMarker })
    .first();
}

function normalizeIso(value: string) {
  return new Date(value).toISOString();
}

async function openAppointmentNoteEditorFromContextMenu(
  page: Page,
  appointmentId: number
) {
  const eventCard = page.getByTestId(`appointment-event-${appointmentId}`);
  await expect(eventCard).toBeVisible({ timeout: 20_000 });
  await eventCard.click({ button: "right" });
  const contextMenu = page.getByTestId("appointments-context-menu");
  await expect(contextMenu).toBeVisible();
  const menuBox = await contextMenu.boundingBox();
  expect(menuBox).not.toBeNull();
  const viewport = page.viewportSize();
  expect(viewport).not.toBeNull();
  expect(menuBox!.x).toBeGreaterThanOrEqual(0);
  expect(menuBox!.y).toBeGreaterThanOrEqual(0);
  expect(menuBox!.x + menuBox!.width).toBeLessThanOrEqual(viewport!.width);
  expect(menuBox!.y + menuBox!.height).toBeLessThanOrEqual(viewport!.height);
  await page.getByTestId("appointments-context-notes").click();
  await expect(page.getByTestId("appointment-detail-panel")).toBeVisible({ timeout: 15_000 });
  return eventCard;
}

test("diary interaction parity: select, open, context menu, escape, enter", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);
  await fs.mkdir(stage158bDir, { recursive: true });
  const patientId = await createPatient(request, {
    first_name: "Diary",
    last_name: `Interaction ${Date.now()}`,
  });
  await createAppointment(request, patientId, {
    starts_at: "2026-01-15T10:00:00.000Z",
    ends_at: "2026-01-15T10:30:00.000Z",
    location_type: "clinic",
    location: "Room 1",
  });
  const baseUrl = getBaseUrl();
  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/appointments?date=2026-01-15&view=day`, {
    waitUntil: "domcontentloaded",
  });
  await waitForDiaryPage(page);

  await page.getByTestId("appointments-view-calendar").click();
  await switchToDayView(page);
  const eventCard = await firstDiaryEvent(page);

  await eventCard.click();
  await expect(eventCard).toHaveClass(/appointments-r4-event--selected/);
  await page.screenshot({
    path: path.join(stage158bDir, "diary_selected_state.png"),
    fullPage: true,
  });

  await eventCard.click({ button: "right" });
  await expect(page.getByTestId("appointments-context-menu")).toBeVisible();
  await expect(page.getByTestId("appointments-context-open")).toBeVisible();
  await expect(page.getByTestId("appointments-context-move")).toBeVisible();
  await expect(page.getByTestId("appointments-context-cancel")).toBeVisible();
  await expect(page.getByTestId("appointments-context-no-show")).toBeVisible();
  await expect(page.getByTestId("appointments-context-notes")).toBeVisible();
  await page.screenshot({
    path: path.join(stage158bDir, "diary_context_menu_open.png"),
    fullPage: true,
  });

  await page.getByRole("heading", { name: "Appointments" }).click();
  await expect(page.getByTestId("appointments-context-menu")).toHaveCount(0);

  await eventCard.click({ button: "right" });
  await expect(page.getByTestId("appointments-context-menu")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("appointments-context-menu")).toHaveCount(0);
  await expect(eventCard).not.toHaveClass(/appointments-r4-event--selected/);

  await eventCard.click();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("appointment-detail-panel")).toBeVisible({ timeout: 15_000 });
  await page.screenshot({
    path: path.join(stage158bDir, "diary_detail_panel_open.png"),
    fullPage: true,
  });
  await page.getByTestId("appointment-detail-close").click();
  await expect(page.getByTestId("appointment-detail-panel")).toHaveCount(0);

  await eventCard.dblclick();
  await expect(page.getByTestId("appointment-detail-panel")).toBeVisible({ timeout: 15_000 });
});

test("diary polish parity: shortcuts and context status action persist", async ({
  page,
  request,
}) => {
  test.setTimeout(150_000);
  await fs.mkdir(stage158dDir, { recursive: true });
  const unique = Date.now();
  const patientId = await createPatient(request, {
    first_name: "Diary",
    last_name: `Shortcut ${unique}`,
  });
  const appointment = await createAppointment(request, patientId, {
    starts_at: "2026-01-15T11:00:00.000Z",
    ends_at: "2026-01-15T11:30:00.000Z",
    location_type: "clinic",
    location: `S158D-${unique}`,
  });

  const baseUrl = getBaseUrl();
  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/appointments?date=2026-01-15&view=day`, {
    waitUntil: "domcontentloaded",
  });
  await waitForDiaryPage(page);
  await page.getByTestId("appointments-view-calendar").click();
  await switchToDayView(page);

  const eventCard = page.getByTestId(`appointment-event-${appointment.id}`);
  await expect(eventCard).toBeVisible({ timeout: 20_000 });
  await eventCard.click({ button: "right" });
  await expect(page.getByTestId("appointments-context-menu")).toBeVisible();
  const arrivedButton = page.getByTestId("appointments-context-arrived");
  await expect(arrivedButton).toBeEnabled();

  let requestCount = 0;
  const routePattern = new RegExp(`/api/appointments/${appointment.id}$`);
  let seenStatusRequest!: () => void;
  const seenStatusRequestPromise = new Promise<void>((resolve) => {
    seenStatusRequest = resolve;
  });
  let releaseStatusRequest!: () => void;
  const releaseStatusRequestPromise = new Promise<void>((resolve) => {
    releaseStatusRequest = resolve;
  });

  await page.route(routePattern, async (route) => {
    if (route.request().method() !== "PATCH") {
      await route.continue();
      return;
    }
    requestCount += 1;
    if (requestCount === 1) {
      expect(route.request().postDataJSON()).toMatchObject({
        status: "arrived",
      });
      seenStatusRequest();
      await releaseStatusRequestPromise;
    }
    await route.continue();
  });

  const statusResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      response.url().includes(`/api/appointments/${appointment.id}`)
  );

  const clickState = await arrivedButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Context status button not found");
    }
    const beforeDisabled = button.disabled;
    button.click();
    const afterFirstDisabled = button.disabled;
    button.click();
    return { beforeDisabled, afterFirstDisabled, afterSecondDisabled: button.disabled };
  });
  await seenStatusRequestPromise;

  expect(clickState.beforeDisabled).toBe(false);
  expect(clickState.afterFirstDisabled).toBe(true);
  expect(clickState.afterSecondDisabled).toBe(true);
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseStatusRequest();

  const statusResponse = await statusResponsePromise;
  expect(statusResponse.ok()).toBeTruthy();
  await expect
    .poll(async () => (await getAppointmentById(request, appointment.id)).status, {
      timeout: 20_000,
    })
    .toBe("arrived");
  await expect(eventCard.locator('[data-status="arrived"]')).toBeVisible();
  await page.screenshot({
    path: path.join(stage158dDir, "context_status_arrived.png"),
    fullPage: true,
  });

  await page.reload({ waitUntil: "domcontentloaded" });
  await waitForDiaryPage(page);
  await page.getByTestId("appointments-view-calendar").click();
  await switchToDayView(page);
  const reloadedEvent = page.getByTestId(`appointment-event-${appointment.id}`);
  await expect(reloadedEvent).toBeVisible({ timeout: 20_000 });
  await expect(reloadedEvent.locator('[data-status="arrived"]')).toBeVisible();

  const diarySearch = page.getByTestId("appointments-diary-search");
  const jumpDateInput = page.getByTestId("appointments-jump-date-input");
  const modKey = process.platform === "darwin" ? "Meta" : "Control";
  await page.keyboard.press(`${modKey}+f`);
  await expect(diarySearch).toBeFocused();
  await diarySearch.fill(String(unique));
  await expect(reloadedEvent).toBeVisible();
  await page.getByRole("heading", { name: "Appointments" }).click();

  await expect(jumpDateInput).toHaveValue("2026-01-15");
  await page.keyboard.press(`${modKey}+ArrowRight`);
  await expect(jumpDateInput).toHaveValue("2026-01-16");
  await page.keyboard.press(`${modKey}+ArrowLeft`);
  await expect(jumpDateInput).toHaveValue("2026-01-15");

  const today = await page.evaluate(() => {
    const value = new Date();
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, "0");
    const day = String(value.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  });
  await page.keyboard.press("t");
  await expect(jumpDateInput).toHaveValue(today);

  await page.keyboard.press("n");
  await expect(page.getByTestId("booking-modal")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("booking-modal")).toHaveCount(0);

  await page.screenshot({
    path: path.join(stage158dDir, "shortcut_navigation.png"),
    fullPage: true,
  });
});

test("diary cut/copy paste guards repeat paste submit", async ({ page, request }) => {
  test.setTimeout(150_000);
  const unique = Date.now();
  const date = "2026-01-16";
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `PASTE${unique}`,
  });
  const appointment = await createAppointment(request, patientId, {
    clinician_user_id: null,
    starts_at: `${date}T12:00:00.000Z`,
    ends_at: `${date}T12:30:00.000Z`,
    location_type: "clinic",
    location: `S163H-PASTE-${unique}`,
  });

  await primePageAuth(page, request);
  await page.setViewportSize({ width: 1400, height: 1200 });
  await page.goto(`${baseUrl}/appointments?date=${date}&view=day`, {
    waitUntil: "domcontentloaded",
  });
  await waitForDiaryPage(page);
  await page.getByTestId("appointments-view-calendar").click();
  await switchToDayView(page);
  const timeContent = page.locator(".rbc-time-content");
  await expect(timeContent).toBeVisible({ timeout: 15_000 });
  const timeContentBox = await timeContent.boundingBox();
  expect(timeContentBox).not.toBeNull();
  await timeContent.click({
    position: {
      x: 350,
      y: Math.min(500, timeContentBox!.height - 40),
    },
  });
  const bookingModal = page.getByTestId("booking-modal");
  await expect(bookingModal).toBeVisible({ timeout: 15_000 });
  await bookingModal.getByRole("button", { name: "Close" }).click();
  await expect(bookingModal).toBeHidden({ timeout: 15_000 });

  const eventCard = page.getByTestId(`appointment-event-${appointment.id}`);
  await expect(eventCard).toBeVisible({ timeout: 20_000 });
  await eventCard.click({ button: "right" });
  await expect(page.getByTestId("appointments-context-menu")).toBeVisible();
  await page.getByTestId("appointments-context-copy").click();
  await expect(
    page.getByText("Copied appointment. Select a slot or appointment to paste.", {
      exact: true,
    })
  ).toBeVisible();

  await page.evaluate(() => {
    window.confirm = () => true;
  });

  let requestCount = 0;
  const routePattern = /\/api\/appointments$/;
  let seenPasteRequest!: () => void;
  const seenPasteRequestPromise = new Promise<void>((resolve) => {
    seenPasteRequest = resolve;
  });
  let releasePasteRequest!: () => void;
  const releasePasteRequestPromise = new Promise<void>((resolve) => {
    releasePasteRequest = resolve;
  });

  await page.route(routePattern, async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    requestCount += 1;
    if (requestCount === 1) {
      seenPasteRequest();
      await releasePasteRequestPromise;
    }
    await route.continue();
  });

  const pasteResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/api/appointments")
  );

  const modKey = process.platform === "darwin" ? "Meta" : "Control";
  await page.getByRole("heading", { name: "Appointments" }).click();
  await page.keyboard.press(`${modKey}+v`);
  await page.keyboard.press(`${modKey}+v`);
  await seenPasteRequestPromise;

  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releasePasteRequest();

  const pasteResponse = await pasteResponsePromise;
  expect(pasteResponse.ok()).toBeTruthy();
  expect(pasteResponse.request().postDataJSON()).toMatchObject({
    patient_id: Number(patientId),
    location: `S163H-PASTE-${unique}`,
    location_type: "clinic",
    status: "booked",
  });
  await page.unroute(routePattern);
});

test("day sheet clipboard cut and copy paste persist after reload", async ({
  page,
  request,
}) => {
  test.setTimeout(180_000);
  const unique = Date.now();
  const date = "2026-01-16";
  const baseUrl = getBaseUrl();
  const modKey = process.platform === "darwin" ? "Meta" : "Control";

  const cutPatientId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `CUT${unique}`,
  });
  const cutTargetPatientId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `CUTTARGET${unique}`,
  });
  const copyPatientId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `COPY${unique}`,
  });
  const copyTargetPatientId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `COPYTARGET${unique}`,
  });

  const cutSource = await createAppointment(request, cutPatientId, {
    starts_at: `${date}T09:00:00.000Z`,
    ends_at: `${date}T09:30:00.000Z`,
    location_type: "clinic",
    location: `S163H-CUT-SOURCE-${unique}`,
  });
  const cutTarget = await createAppointment(request, cutTargetPatientId, {
    starts_at: `${date}T10:00:00.000Z`,
    ends_at: `${date}T10:30:00.000Z`,
    location_type: "clinic",
    location: `S163H-CUT-TARGET-${unique}`,
  });
  const copySource = await createAppointment(request, copyPatientId, {
    starts_at: `${date}T11:00:00.000Z`,
    ends_at: `${date}T11:30:00.000Z`,
    location_type: "clinic",
    location: `S163H-COPY-SOURCE-${unique}`,
  });
  const copyTarget = await createAppointment(request, copyTargetPatientId, {
    starts_at: `${date}T12:00:00.000Z`,
    ends_at: `${date}T12:30:00.000Z`,
    location_type: "clinic",
    location: `S163H-COPY-TARGET-${unique}`,
  });

  await primePageAuth(page, request);
  await page.setViewportSize({ width: 1400, height: 1200 });
  await page.goto(`${baseUrl}/appointments?date=${date}`, {
    waitUntil: "domcontentloaded",
  });
  await waitForDiaryPage(page);
  await page.getByTestId("appointments-view-day-sheet").click();

  const cutSourceRow = daySheetRow(page, `CUT${unique}`);
  const cutTargetRow = daySheetRow(page, `CUTTARGET${unique}`);
  const copySourceRow = daySheetRow(page, `COPY${unique}`);
  const copyTargetRow = daySheetRow(page, `COPYTARGET${unique}`);

  await expect(cutSourceRow).toBeVisible({ timeout: 20_000 });
  await expect(cutTargetRow).toBeVisible({ timeout: 20_000 });
  await expect(copySourceRow).toBeVisible({ timeout: 20_000 });
  await expect(copyTargetRow).toBeVisible({ timeout: 20_000 });

  await page.evaluate(() => {
    window.confirm = () => true;
  });

  await cutSourceRow.click({ button: "right" });
  await expect(page.getByTestId("appointments-context-menu")).toBeVisible();
  await page.getByTestId("appointments-context-move").click();
  await expect(
    page.getByText("Move mode enabled. Select a slot or appointment to paste.", {
      exact: true,
    })
  ).toBeVisible();
  let cutRequestCount = 0;
  const cutRoutePattern = new RegExp(`/api/appointments/${cutSource.id}$`);
  await page.route(cutRoutePattern, async (route) => {
    if (route.request().method() !== "PATCH") {
      await route.continue();
      return;
    }
    cutRequestCount += 1;
    await route.continue();
  });
  await page.keyboard.press(`${modKey}+v`);
  await expect(
    page.getByText("Select a slot or appointment before pasting.", { exact: true })
  ).toBeVisible({ timeout: 15_000 });
  await page.waitForTimeout(250);
  expect(cutRequestCount).toBe(0);
  await cutTargetRow.click();

  const cutRequestPromise = page.waitForRequest(
    (request) =>
      request.method() === "PATCH" &&
      request.url().includes(`/api/appointments/${cutSource.id}`)
  );
  const cutResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      response.url().includes(`/api/appointments/${cutSource.id}`)
  );
  await page.keyboard.press(`${modKey}+v`);

  const cutRequest = await cutRequestPromise;
  const cutPayload = cutRequest.postDataJSON() as { starts_at: string; ends_at: string };
  expect(normalizeIso(cutPayload.starts_at)).toBe(normalizeIso(cutTarget.starts_at));
  expect(normalizeIso(cutPayload.ends_at)).toBe(normalizeIso(cutTarget.ends_at));
  const cutResponse = await cutResponsePromise;
  expect(cutResponse.ok()).toBeTruthy();
  expect(cutRequestCount).toBe(1);
  await expect(page.getByText("Moved appointment.", { exact: true })).toBeVisible({
    timeout: 15_000,
  });
  await expect
    .poll(async () => normalizeIso((await getAppointmentById(request, cutSource.id)).starts_at), {
      timeout: 20_000,
    })
    .toBe(normalizeIso(cutTarget.starts_at));
  await expect
    .poll(async () => normalizeIso((await getAppointmentById(request, cutSource.id)).ends_at), {
      timeout: 20_000,
    })
    .toBe(normalizeIso(cutTarget.ends_at));

  await copySourceRow.click({ button: "right" });
  await expect(page.getByTestId("appointments-context-menu")).toBeVisible();
  await page.getByTestId("appointments-context-copy").click();
  await expect(
    page.getByText("Copied appointment. Select a slot or appointment to paste.", {
      exact: true,
    })
  ).toBeVisible();
  let copyRequestCount = 0;
  const copyRoutePattern = /\/api\/appointments$/;
  await page.route(copyRoutePattern, async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    copyRequestCount += 1;
    await route.continue();
  });
  await page.keyboard.press(`${modKey}+v`);
  await expect(
    page.getByText("Select a slot or appointment before pasting.", { exact: true })
  ).toBeVisible({ timeout: 15_000 });
  await page.waitForTimeout(250);
  expect(copyRequestCount).toBe(0);
  await copyTargetRow.click();

  const copyRequestPromise = page.waitForRequest(
    (request) => request.method() === "POST" && request.url().endsWith("/api/appointments")
  );
  const copyResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/api/appointments")
  );
  await page.keyboard.press(`${modKey}+v`);

  const copyRequest = await copyRequestPromise;
  const copyPayload = copyRequest.postDataJSON() as {
    patient_id: number;
    starts_at: string;
    ends_at: string;
    location?: string | null;
    location_type: "clinic" | "visit";
    status: string;
  };
  expect(copyPayload).toMatchObject({
    patient_id: Number(copyPatientId),
    location: copySource.location,
    location_type: copySource.location_type,
    status: "booked",
  });
  expect(normalizeIso(copyPayload.starts_at)).toBe(normalizeIso(copyTarget.starts_at));
  expect(normalizeIso(copyPayload.ends_at)).toBe(normalizeIso(copyTarget.ends_at));
  const copyResponse = await copyResponsePromise;
  expect(copyResponse.ok()).toBeTruthy();
  expect(copyRequestCount).toBe(1);
  const copiedAppointment = (await copyResponse.json()) as AppointmentDetails;
  expect(copiedAppointment.id).toBeGreaterThan(0);
  expect(copiedAppointment.id).not.toBe(copySource.id);
  await expect(page.getByText("Copied appointment.", { exact: true })).toBeVisible({
    timeout: 15_000,
  });
  await expect
    .poll(
      async () => normalizeIso((await getAppointmentById(request, copiedAppointment.id)).starts_at),
      {
        timeout: 20_000,
      }
    )
    .toBe(normalizeIso(copyTarget.starts_at));
  await expect
    .poll(
      async () => normalizeIso((await getAppointmentById(request, copiedAppointment.id)).ends_at),
      {
        timeout: 20_000,
      }
    )
    .toBe(normalizeIso(copyTarget.ends_at));

  await page.reload({ waitUntil: "domcontentloaded" });
  await waitForDiaryPage(page);
  await page.getByTestId("appointments-view-day-sheet").click();

  await expect(daySheetRow(page, `CUT${unique}`)).toBeVisible({ timeout: 20_000 });
  await expect(
    page.locator(".day-sheet-table tbody tr").filter({ hasText: `COPY${unique}` })
  ).toHaveCount(2);
  await expect
    .poll(async () => normalizeIso((await getAppointmentById(request, cutSource.id)).starts_at), {
      timeout: 20_000,
    })
    .toBe(normalizeIso(cutTarget.starts_at));
  await expect
    .poll(
      async () => normalizeIso((await getAppointmentById(request, copiedAppointment.id)).starts_at),
      {
        timeout: 20_000,
      }
    )
    .toBe(normalizeIso(copyTarget.starts_at));
  await page.unroute(cutRoutePattern);
  await page.unroute(copyRoutePattern);
});

test("appointment detail notes stay scoped to the selected appointment and refresh row state", async ({
  page,
  request,
}) => {
  test.setTimeout(150_000);
  const unique = Date.now();
  const date = "2026-01-16";
  const baseUrl = getBaseUrl();
  const patientWithNotesId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `APPTA${unique}`,
  });
  const patientWithoutNotesId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `APPTB${unique}`,
  });
  const appointmentWithNotes = await createAppointment(request, patientWithNotesId, {
    starts_at: `${date}T09:00:00.000Z`,
    ends_at: `${date}T09:30:00.000Z`,
    location_type: "clinic",
    location: `S163H-A-${unique}`,
  });
  const appointmentWithoutNotes = await createAppointment(request, patientWithoutNotesId, {
    starts_at: `${date}T10:00:00.000Z`,
    ends_at: `${date}T10:30:00.000Z`,
    location_type: "clinic",
    location: `S163H-B-${unique}`,
  });
  const existingNote = `Existing appointment note ${unique}`;
  const newNote = `Fresh drawer note ${unique}`;

  await createAppointmentNote(request, appointmentWithNotes.id, {
    body: existingNote,
  });

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/appointments?date=${date}`, {
    waitUntil: "domcontentloaded",
  });
  await waitForDiaryPage(page);
  await page.getByTestId("appointments-view-day-sheet").click();

  const firstRow = page
    .locator(".day-sheet-table tbody tr")
    .filter({ hasText: `APPTA${unique}` })
    .first();
  const secondRow = page
    .locator(".day-sheet-table tbody tr")
    .filter({ hasText: `APPTB${unique}` })
    .first();
  await expect(firstRow).toBeVisible({ timeout: 20_000 });
  await expect(secondRow).toBeVisible({ timeout: 20_000 });

  await firstRow.click();
  await expect(firstRow).toHaveClass(/row-highlight/);
  await page.keyboard.press("Enter");
  const detailPanel = page.getByTestId("appointment-detail-panel");
  const quickNote = detailPanel.getByPlaceholder("Add a brief clinical note");
  await expect(detailPanel).toBeVisible({ timeout: 15_000 });
  await expect(detailPanel).toContainText(`APPTA${unique}`);
  await expect(detailPanel.getByText(existingNote)).toBeVisible();

  await quickNote.fill("Unsaved note draft should not leak");
  await page.getByTestId("appointment-detail-close").click();
  await expect(detailPanel).toHaveCount(0);

  await secondRow.click();
  await expect(secondRow).toHaveClass(/row-highlight/);
  await page.keyboard.press("Enter");
  await expect(detailPanel).toBeVisible({ timeout: 15_000 });
  await expect(detailPanel).toContainText(`APPTB${unique}`);
  await expect(quickNote).toHaveValue("");
  await expect(detailPanel.getByText("No notes yet.")).toBeVisible();
  await expect(detailPanel.getByText(existingNote)).toHaveCount(0);

  await quickNote.fill(newNote);
  await detailPanel.getByRole("button", { name: "Add note" }).click();
  await expect(detailPanel.getByText(newNote)).toBeVisible({ timeout: 15_000 });

  await page.getByTestId("appointment-detail-close").click();
  await expect(secondRow.locator(".day-sheet-note-icon")).toBeVisible({ timeout: 15_000 });
});

test("appointment detail Add note shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  test.setTimeout(150_000);
  const unique = Date.now();
  const date = "2026-01-16";
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `NOTE${unique}`,
  });
  const appointment = await createAppointment(request, patientId, {
    starts_at: `${date}T11:00:00.000Z`,
    ends_at: `${date}T11:30:00.000Z`,
    location_type: "clinic",
    location: `S163H-NOTE-${unique}`,
  });
  const newNote = `Appointment repeat-submit note ${unique}`;

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/appointments?date=${date}`, {
    waitUntil: "domcontentloaded",
  });
  await waitForDiaryPage(page);
  await page.getByTestId("appointments-view-day-sheet").click();

  const row = page
    .locator(".day-sheet-table tbody tr")
    .filter({ hasText: `NOTE${unique}` })
    .first();
  await expect(row).toBeVisible({ timeout: 20_000 });
  await row.click();
  await expect(row).toHaveClass(/row-highlight/);
  await page.keyboard.press("Enter");

  const detailPanel = page.getByTestId("appointment-detail-panel");
  await expect(detailPanel).toBeVisible({ timeout: 15_000 });
  await expect(detailPanel).toContainText(`NOTE${unique}`);
  await expect(detailPanel.getByText("No notes yet.")).toBeVisible({ timeout: 15_000 });

  const quickNote = detailPanel.getByPlaceholder("Add a brief clinical note");
  await quickNote.fill(newNote);

  const addNoteButton = detailPanel.getByTestId("appointment-detail-add-note");
  await expect(addNoteButton).toBeEnabled();

  let requestCount = 0;
  const routePattern = new RegExp(`/api/appointments/${appointment.id}/notes$`);
  let seenCreateRequest!: () => void;
  const seenCreateRequestPromise = new Promise<void>((resolve) => {
    seenCreateRequest = resolve;
  });
  let releaseCreateRequest!: () => void;
  const releaseCreateRequestPromise = new Promise<void>((resolve) => {
    releaseCreateRequest = resolve;
  });
  let holdReloadRequest = false;
  let reloadRequestCount = 0;
  let seenReloadRequest!: () => void;
  const seenReloadRequestPromise = new Promise<void>((resolve) => {
    seenReloadRequest = resolve;
  });
  let releaseReloadRequest!: () => void;
  const releaseReloadRequestPromise = new Promise<void>((resolve) => {
    releaseReloadRequest = resolve;
  });
  const reloadResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      response.url().includes(`/api/appointments/${appointment.id}/notes`)
  );

  await page.route(routePattern, async (route) => {
    if (route.request().method() === "GET") {
      if (!holdReloadRequest) {
        await route.continue();
        return;
      }
      reloadRequestCount += 1;
      if (reloadRequestCount === 1) {
        seenReloadRequest();
        await releaseReloadRequestPromise;
      }
      await route.continue();
      return;
    }
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
      response.url().includes(`/api/appointments/${appointment.id}/notes`)
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

  holdReloadRequest = true;
  releaseCreateRequest();

  const createResponse = await createResponsePromise;
  expect(createResponse.ok()).toBeTruthy();
  expect(createResponse.request().postDataJSON()).toMatchObject({
    body: newNote,
    note_type: "clinical",
  });

  await seenReloadRequestPromise;
  await expect(detailPanel.getByText(newNote)).toBeVisible({ timeout: 15_000 });
  await page.waitForTimeout(250);
  expect(reloadRequestCount).toBe(1);

  releaseReloadRequest();
  const reloadResponse = await reloadResponsePromise;
  expect(reloadResponse.ok()).toBeTruthy();
  await page.unroute(routePattern);

  await expect(addNoteButton).toBeEnabled({ timeout: 15_000 });
  await expect(addNoteButton).toHaveText("Add note");
  await expect(detailPanel.getByText(newNote)).toBeVisible({ timeout: 15_000 });
  await page.getByTestId("appointment-detail-close").click();
  await expect(row.locator(".day-sheet-note-icon")).toBeVisible({ timeout: 15_000 });
});

test("calendar context-menu Add note keeps drawer state scoped and refreshes visible note state", async ({
  page,
  request,
}) => {
  test.setTimeout(150_000);
  const unique = Date.now();
  const date = "2026-01-16";
  const baseUrl = getBaseUrl();
  const patientWithNotesId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `CTXA${unique}`,
  });
  const patientWithoutNotesId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `CTXB${unique}`,
  });
  const appointmentWithNotes = await createAppointment(request, patientWithNotesId, {
    starts_at: `${date}T09:00:00.000Z`,
    ends_at: `${date}T09:30:00.000Z`,
    location_type: "clinic",
    location: `S163H-CAL-A-${unique}`,
  });
  const appointmentWithoutNotes = await createAppointment(request, patientWithoutNotesId, {
    starts_at: `${date}T10:00:00.000Z`,
    ends_at: `${date}T10:30:00.000Z`,
    location_type: "clinic",
    location: `S163H-CAL-B-${unique}`,
  });
  const existingNote = `Calendar existing note ${unique}`;
  const newNote = `Calendar added note ${unique}`;

  await createAppointmentNote(request, appointmentWithNotes.id, {
    body: existingNote,
  });

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/appointments?date=${date}&view=day`, {
    waitUntil: "domcontentloaded",
  });
  await waitForDiaryPage(page);
  await page.getByTestId("appointments-view-calendar").click();
  await switchToDayView(page);

  await openAppointmentNoteEditorFromContextMenu(page, appointmentWithNotes.id);
  const detailPanel = page.getByTestId("appointment-detail-panel");
  const editNote = detailPanel.getByPlaceholder("Add a note for this appointment");
  await expect(detailPanel).toContainText(`CTXA${unique}`);
  await expect(editNote).toHaveValue("");
  await editNote.fill("Unsaved calendar note draft should not leak");
  await page.getByTestId("appointment-detail-close").click();
  await expect(detailPanel).toHaveCount(0);

  await openAppointmentNoteEditorFromContextMenu(page, appointmentWithoutNotes.id);
  await expect(detailPanel).toContainText(`CTXB${unique}`);
  await expect(editNote).toHaveValue("");

  await editNote.fill(newNote);
  await detailPanel.getByRole("button", { name: "Save changes" }).click();
  await expect(detailPanel.getByPlaceholder("Add a note for this appointment")).toHaveCount(0);
  await expect(detailPanel.getByText(newNote)).toBeVisible({ timeout: 15_000 });
  await expect(detailPanel.getByText(existingNote)).toHaveCount(0);

  await page.getByTestId("appointment-detail-close").click();
  await page.getByTestId("appointments-view-day-sheet").click();
  const secondRow = page
    .locator(".day-sheet-table tbody tr")
    .filter({ hasText: `CTXB${unique}` })
    .first();
  await expect(secondRow.locator(".day-sheet-note-icon")).toBeVisible({ timeout: 15_000 });
});

test("appointment drawer note actions use appointment-scoped edit save archive restore routes and guard repeat archive submit", async ({
  page,
  request,
}) => {
  test.setTimeout(150_000);
  const unique = Date.now();
  const date = "2026-01-16";
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `ACT${unique}`,
  });
  const appointment = await createAppointment(request, patientId, {
    starts_at: `${date}T09:00:00.000Z`,
    ends_at: `${date}T09:30:00.000Z`,
    location_type: "clinic",
    location: `S163H-ACT-${unique}`,
  });
  const createdNote = await createAppointmentNote(request, appointment.id, {
    body: `Appointment note actions ${unique}`,
  });
  const updatedNote = `Appointment note updated ${unique}`;
  const updatedType = "admin";

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/appointments?date=${date}`, {
    waitUntil: "domcontentloaded",
  });
  await waitForDiaryPage(page);
  await page.getByTestId("appointments-view-day-sheet").click();

  const row = page
    .locator(".day-sheet-table tbody tr")
    .filter({ hasText: `ACT${unique}` })
    .first();
  await expect(row).toBeVisible({ timeout: 20_000 });

  await row.click();
  await page.keyboard.press("Enter");

  const detailPanel = page.getByTestId("appointment-detail-panel");
  await expect(detailPanel).toBeVisible({ timeout: 15_000 });
  await expect(detailPanel.getByText(createdNote.body)).toBeVisible({ timeout: 15_000 });

  await detailPanel.locator('[data-testid^="appointment-note-edit-"]').first().click();
  await detailPanel
    .locator('[data-testid^="appointment-note-edit-type-"]')
    .first()
    .selectOption(updatedType);
  await detailPanel
    .locator('[data-testid^="appointment-note-edit-body-"]')
    .first()
    .fill(updatedNote);
  const saveNoteButton = detailPanel.getByTestId(`appointment-note-save-${createdNote.id}`);
  await expect(saveNoteButton).toBeEnabled();

  let requestCount = 0;
  const routePattern = new RegExp(
    `/api/appointments/${appointment.id}/notes/${createdNote.id}$`
  );
  let seenEditRequest!: () => void;
  const seenEditRequestPromise = new Promise<void>((resolve) => {
    seenEditRequest = resolve;
  });
  let releaseEditRequest!: () => void;
  const releaseEditRequestPromise = new Promise<void>((resolve) => {
    releaseEditRequest = resolve;
  });

  await page.route(routePattern, async (route) => {
    if (route.request().method() !== "PATCH") {
      await route.continue();
      return;
    }
    requestCount += 1;
    if (requestCount === 1) {
      expect(route.request().postDataJSON()).toMatchObject({
        body: updatedNote,
        note_type: updatedType,
      });
      seenEditRequest();
      await releaseEditRequestPromise;
    }
    await route.continue();
  });

  const editResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      response.url().includes(
        `/api/appointments/${appointment.id}/notes/${createdNote.id}`
      )
  );

  const clickState = await saveNoteButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Save note button not found");
    }
    const beforeDisabled = button.disabled;
    button.click();
    const afterFirstDisabled = button.disabled;
    button.click();
    return { beforeDisabled, afterFirstDisabled, afterSecondDisabled: button.disabled };
  });
  await seenEditRequestPromise;

  expect(clickState.beforeDisabled).toBe(false);
  expect(clickState.afterFirstDisabled).toBe(true);
  expect(clickState.afterSecondDisabled).toBe(true);
  await expect(saveNoteButton).toBeDisabled();
  await expect(saveNoteButton).toHaveText("Saving...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseEditRequest();

  const editResponse = await editResponsePromise;
  expect(editResponse.ok()).toBeTruthy();
  await expect(detailPanel.getByText(updatedNote)).toBeVisible({ timeout: 15_000 });
  await expect(
    detailPanel
      .getByTestId(`appointment-note-card-${createdNote.id}`)
      .getByText("Admin", { exact: true })
  ).toBeVisible({ timeout: 15_000 });

  const archiveButton = detailPanel.getByTestId(`appointment-note-archive-${createdNote.id}`);
  await expect(archiveButton).toBeEnabled();
  await page.evaluate(() => {
    window.confirm = () => true;
  });

  let archiveRequestCount = 0;
  const archiveRoutePattern = new RegExp(
    `/api/appointments/${appointment.id}/notes/${createdNote.id}/archive$`
  );
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
    archiveRequestCount += 1;
    if (archiveRequestCount === 1) {
      seenArchiveRequest();
      await releaseArchiveRequestPromise;
    }
    await route.continue();
  });

  const archiveResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().includes(
        `/api/appointments/${appointment.id}/notes/${createdNote.id}/archive`
      )
  );
  const archiveClickState = await archiveButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Archive note button not found");
    }
    const beforeDisabled = button.disabled;
    button.click();
    const afterFirstDisabled = button.disabled;
    button.click();
    return { beforeDisabled, afterFirstDisabled, afterSecondDisabled: button.disabled };
  });
  await seenArchiveRequestPromise;

  expect(archiveClickState.beforeDisabled).toBe(false);
  expect(archiveClickState.afterFirstDisabled).toBe(true);
  expect(archiveClickState.afterSecondDisabled).toBe(true);
  await expect(archiveButton).toBeDisabled();
  await expect(archiveButton).toHaveText("Archiving...");
  await page.waitForTimeout(250);
  expect(archiveRequestCount).toBe(1);

  releaseArchiveRequest();

  const archiveResponse = await archiveResponsePromise;
  expect(archiveResponse.ok()).toBeTruthy();
  await expect(detailPanel.getByText("No notes yet.")).toBeVisible({ timeout: 15_000 });

  await page.getByTestId("appointment-detail-close").click();
  await expect(row.locator(".day-sheet-note-icon")).toHaveCount(0);

  await row.click();
  await page.keyboard.press("Enter");
  await expect(detailPanel).toBeVisible({ timeout: 15_000 });
  await detailPanel.getByTestId("appointments-notes-show-archived").check();
  await expect(detailPanel.getByText(updatedNote)).toBeVisible({ timeout: 15_000 });

  const restoreResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().includes(
        `/api/appointments/${appointment.id}/notes/${createdNote.id}/restore`
      )
  );
  await detailPanel.locator('[data-testid^="appointment-note-restore-"]').first().click();
  const restoreResponse = await restoreResponsePromise;
  expect(restoreResponse.ok()).toBeTruthy();
  await expect(detailPanel.getByText(updatedNote)).toBeVisible({ timeout: 15_000 });

  await page.getByTestId("appointment-detail-close").click();
  await expect(row.locator(".day-sheet-note-icon")).toBeVisible({ timeout: 15_000 });
});

test("diary cancel appointment keeps modal state in-flight and guards repeat submit", async ({
  page,
  request,
}) => {
  test.setTimeout(150_000);
  const unique = Date.now();
  const date = "2026-01-16";
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `CANCEL${unique}`,
  });
  const appointment = await createAppointment(request, patientId, {
    starts_at: `${date}T14:00:00.000Z`,
    ends_at: `${date}T14:30:00.000Z`,
    location_type: "clinic",
    location: `S163H-CANCEL-${unique}`,
  });

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/appointments?date=${date}&view=day`, {
    waitUntil: "domcontentloaded",
  });
  await waitForDiaryPage(page);
  await page.getByTestId("appointments-view-calendar").click();
  await switchToDayView(page);

  const eventCard = page.getByTestId(`appointment-event-${appointment.id}`);
  await expect(eventCard).toBeVisible({ timeout: 20_000 });
  await eventCard.click({ button: "right" });
  await expect(page.getByTestId("appointments-context-menu")).toBeVisible();
  await page.getByTestId("appointments-context-cancel").click();

  const reason = `Patient cancelled ${unique}`;
  const cancelTextarea = page.getByPlaceholder(
    "Patient cancelled, clinician unavailable, etc."
  );
  await expect(cancelTextarea).toBeVisible({ timeout: 15_000 });
  await cancelTextarea.fill(reason);
  const confirmButton = page.getByTestId("appointments-cancel-confirm");
  await expect(confirmButton).toBeEnabled();

  let requestCount = 0;
  const routePattern = new RegExp(`/api/appointments/${appointment.id}$`);
  let seenCancelRequest!: () => void;
  const seenCancelRequestPromise = new Promise<void>((resolve) => {
    seenCancelRequest = resolve;
  });
  let releaseCancelRequest!: () => void;
  const releaseCancelRequestPromise = new Promise<void>((resolve) => {
    releaseCancelRequest = resolve;
  });

  await page.route(routePattern, async (route) => {
    if (route.request().method() !== "PATCH") {
      await route.continue();
      return;
    }
    requestCount += 1;
    if (requestCount === 1) {
      expect(route.request().postDataJSON()).toMatchObject({
        status: "cancelled",
        cancel_reason: reason,
      });
      seenCancelRequest();
      await releaseCancelRequestPromise;
    }
    await route.continue();
  });

  const cancelResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      response.url().includes(`/api/appointments/${appointment.id}`)
  );

  const clickState = await confirmButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Cancel confirm button not found");
    }
    const beforeDisabled = button.disabled;
    button.click();
    const afterFirstDisabled = button.disabled;
    button.click();
    return { beforeDisabled, afterFirstDisabled, afterSecondDisabled: button.disabled };
  });
  await seenCancelRequestPromise;

  expect(clickState.beforeDisabled).toBe(false);
  expect(clickState.afterFirstDisabled).toBe(true);
  expect(clickState.afterSecondDisabled).toBe(true);
  await expect(confirmButton).toBeDisabled();
  await expect(confirmButton).toHaveText("Cancelling...");
  await expect(cancelTextarea).toBeDisabled();
  await expect(cancelTextarea).toHaveValue(reason);
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseCancelRequest();

  const cancelResponse = await cancelResponsePromise;
  expect(cancelResponse.ok()).toBeTruthy();
  await expect(confirmButton).toHaveCount(0);
  await expect(cancelTextarea).toHaveCount(0);
  await expect
    .poll(async () => (await getAppointmentById(request, appointment.id)).status, {
      timeout: 20_000,
    })
    .toBe("cancelled");
  await expect(
    page
      .getByTestId(`appointment-event-${appointment.id}`)
      .locator('[data-status="cancelled"]')
  ).toBeVisible({ timeout: 20_000 });
});
