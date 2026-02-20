import fs from "node:fs/promises";
import path from "node:path";

import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import { createAppointment, createPatient } from "./helpers/api";
import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

const stage158cDir = path.resolve(__dirname, "..", "..", ".run", "stage158c");

type AppointmentDetails = {
  id: number;
  starts_at: string;
  ends_at: string;
  location?: string | null;
  status: string;
};

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

async function setAppointmentStatus(
  request: APIRequestContext,
  appointmentId: number,
  status: "cancelled" | "no_show"
) {
  const token = await ensureAuthReady(request);
  const baseUrl = getBaseUrl();
  const response = await request.patch(`${baseUrl}/api/appointments/${appointmentId}`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      status,
      cancel_reason: "Stage158C lane marker",
    },
  });
  expect(response.ok()).toBeTruthy();
}

test("diary drag/drop + resize parity: move lane/time, resize, and block overlap", async ({
  page,
  request,
}) => {
  test.setTimeout(180_000);
  await fs.mkdir(stage158cDir, { recursive: true });
  const baseUrl = getBaseUrl();
  const unique = Date.now();
  const testDate = "2026-03-17";
  const sourceRoom = `S158C-From-${unique}`;
  const targetRoom = `S158C-To-${unique}`;

  const patient1 = await createPatient(request, {
    first_name: "Stage158C",
    last_name: `Move ${unique}`,
  });
  const patient2 = await createPatient(request, {
    first_name: "Stage158C",
    last_name: `LaneTarget ${unique}`,
  });
  const patient3 = await createPatient(request, {
    first_name: "Stage158C",
    last_name: `Overlap ${unique}`,
  });

  const movable = await createAppointment(request, patient1, {
    starts_at: `${testDate}T10:00:00.000Z`,
    ends_at: `${testDate}T10:30:00.000Z`,
    location_type: "clinic",
    location: sourceRoom,
  });
  const cancelledLaneTarget = await createAppointment(request, patient2, {
    starts_at: `${testDate}T11:00:00.000Z`,
    ends_at: `${testDate}T11:30:00.000Z`,
    location_type: "clinic",
    location: targetRoom,
  });
  const overlapBlocker = await createAppointment(request, patient3, {
    starts_at: `${testDate}T12:00:00.000Z`,
    ends_at: `${testDate}T12:30:00.000Z`,
    location_type: "clinic",
    location: targetRoom,
  });

  await setAppointmentStatus(request, cancelledLaneTarget.id, "cancelled");

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/appointments?date=${testDate}&view=day`, {
    waitUntil: "domcontentloaded",
  });
  await waitForDiaryPage(page);
  await page.getByTestId("appointments-view-calendar").click();
  await switchToDayView(page);

  const movableEvent = page.getByTestId(`appointment-event-${movable.id}`);
  const laneTargetEvent = page.getByTestId(`appointment-event-${cancelledLaneTarget.id}`);
  const overlapEvent = page.getByTestId(`appointment-event-${overlapBlocker.id}`);

  await expect(movableEvent).toBeVisible({ timeout: 20_000 });
  await expect(laneTargetEvent).toBeVisible({ timeout: 20_000 });
  await expect(overlapEvent).toBeVisible({ timeout: 20_000 });

  await movableEvent.dragTo(laneTargetEvent);
  await expect
    .poll(async () => (await getAppointmentById(request, movable.id)).location ?? "", {
      timeout: 20_000,
    })
    .toBe(targetRoom);
  await expect
    .poll(async () => (await getAppointmentById(request, movable.id)).starts_at, {
      timeout: 20_000,
    })
    .toContain(`${testDate}T11:00`);
  await page.screenshot({
    path: path.join(stage158cDir, "drag_move.png"),
    fullPage: true,
  });

  const resizableEvent = page
    .locator(".rbc-addons-dnd-resizable", {
      has: page.getByTestId(`appointment-event-${movable.id}`),
    })
    .first();
  await resizableEvent.hover();
  const resizeHandle = resizableEvent
    .locator(".rbc-addons-dnd-resize-ns-anchor")
    .last();
  await expect(resizeHandle).toBeVisible({ timeout: 15_000 });
  const laneTimeColumn = page.locator(".rbc-time-content .rbc-day-slot").first();
  const slotA = await laneTimeColumn.locator(".rbc-time-slot").nth(0).boundingBox();
  const slotB = await laneTimeColumn.locator(".rbc-time-slot").nth(1).boundingBox();
  const handleBox = await resizeHandle.boundingBox();
  if (!slotA || !slotB || !handleBox) {
    throw new Error("Unable to compute slot or resize handle geometry.");
  }
  const slotStep = Math.max(6, slotB.y - slotA.y);
  const handleX = handleBox.x + handleBox.width / 2;
  const handleY = handleBox.y + handleBox.height / 2;
  await page.mouse.move(handleX, handleY);
  await page.mouse.down();
  await page.mouse.move(handleX, handleY + slotStep * 3 + 2, { steps: 10 });
  await page.mouse.up();
  await expect
    .poll(async () => {
      const appt = await getAppointmentById(request, movable.id);
      return Math.round(
        (new Date(appt.ends_at).getTime() - new Date(appt.starts_at).getTime()) / 60000
      );
    }, { timeout: 20_000 })
    .toBeGreaterThan(30);
  await page.screenshot({
    path: path.join(stage158cDir, "resize.png"),
    fullPage: true,
  });

  const beforeOverlapAttempt = await getAppointmentById(request, movable.id);
  await movableEvent.dragTo(overlapEvent);
  await expect
    .poll(async () => (await getAppointmentById(request, movable.id)).starts_at, {
      timeout: 20_000,
    })
    .toBe(beforeOverlapAttempt.starts_at);
  await expect
    .poll(async () => (await getAppointmentById(request, movable.id)).location ?? "", {
      timeout: 20_000,
    })
    .toBe(targetRoom);
  await page.screenshot({
    path: path.join(stage158cDir, "overlap_blocked.png"),
    fullPage: true,
  });
});
