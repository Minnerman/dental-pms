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

async function openAppointmentNoteEditorFromContextMenu(
  page: Page,
  appointmentId: number
) {
  const eventCard = page.getByTestId(`appointment-event-${appointmentId}`);
  await expect(eventCard).toBeVisible({ timeout: 20_000 });
  await eventCard.click({ button: "right" });
  await expect(page.getByTestId("appointments-context-menu")).toBeVisible();
  await page
    .getByTestId("appointments-context-notes")
    .evaluate((element) => (element as HTMLButtonElement).click());
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
  await page.getByTestId("appointments-context-arrived").click();
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

  await createAppointmentNote(request, patientWithNotesId, appointmentWithNotes.id, {
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

  await createAppointmentNote(request, patientWithNotesId, appointmentWithNotes.id, {
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
