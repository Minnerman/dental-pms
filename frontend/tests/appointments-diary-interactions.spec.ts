import fs from "node:fs/promises";
import path from "node:path";

import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import { createAppointment, createPatient } from "./helpers/api";
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
