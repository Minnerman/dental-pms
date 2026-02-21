import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import { createAppointment, createPatient } from "./helpers/api";
import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

type SnapshotAppointment = {
  id: number;
  starts_at: string;
  ends_at: string;
  duration_minutes: number;
  status: "booked" | "arrived" | "in_progress" | "completed" | "cancelled" | "no_show";
  location?: string | null;
  location_type: "clinic" | "visit";
};

type SnapshotResponse = {
  appointments: SnapshotAppointment[];
};

function minutesFromIso(value: string) {
  const date = new Date(value);
  return date.getHours() * 60 + date.getMinutes();
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

async function setAppointmentStatus(
  request: APIRequestContext,
  appointmentId: number,
  status: "arrived" | "completed" | "cancelled"
) {
  const token = await ensureAuthReady(request);
  const baseUrl = getBaseUrl();
  const response = await request.patch(`${baseUrl}/api/appointments/${appointmentId}`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      status,
      cancel_reason: status === "cancelled" ? "Stage159 lane marker" : undefined,
    },
  });
  expect(response.ok()).toBeTruthy();
}

async function getSnapshotForDate(
  request: APIRequestContext,
  date: string
): Promise<SnapshotResponse> {
  const token = await ensureAuthReady(request);
  const baseUrl = getBaseUrl();
  const response = await request.get(
    `${baseUrl}/api/appointments/snapshot?date=${date}&view=day&mask_names=true`,
    {
      headers: { Authorization: `Bearer ${token}` },
    }
  );
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as SnapshotResponse;
}

test("diary hardening: sampled start-time positioning + status visual mapping parity", async ({
  page,
  request,
}) => {
  test.setTimeout(150_000);
  const unique = Date.now();
  const date = "2026-04-14";
  const baseUrl = getBaseUrl();

  const patientBooked = await createPatient(request, {
    first_name: "Stage159",
    last_name: `Booked ${unique}`,
  });
  const patientArrived = await createPatient(request, {
    first_name: "Stage159",
    last_name: `Arrived ${unique}`,
  });
  const patientCompleted = await createPatient(request, {
    first_name: "Stage159",
    last_name: `Completed ${unique}`,
  });

  const booked = await createAppointment(request, patientBooked, {
    starts_at: `${date}T09:00:00.000Z`,
    ends_at: `${date}T09:30:00.000Z`,
    location_type: "clinic",
    location: `S159-A-${unique}`,
  });
  const arrived = await createAppointment(request, patientArrived, {
    starts_at: `${date}T09:30:00.000Z`,
    ends_at: `${date}T10:00:00.000Z`,
    location_type: "clinic",
    location: `S159-B-${unique}`,
  });
  const completed = await createAppointment(request, patientCompleted, {
    starts_at: `${date}T10:00:00.000Z`,
    ends_at: `${date}T10:30:00.000Z`,
    location_type: "clinic",
    location: `S159-C-${unique}`,
  });

  await setAppointmentStatus(request, arrived.id, "arrived");
  await setAppointmentStatus(request, completed.id, "completed");

  const snapshot = await getSnapshotForDate(request, date);
  const byId = new Map(snapshot.appointments.map((item) => [item.id, item]));
  expect(byId.get(booked.id)?.status).toBe("booked");
  expect(byId.get(arrived.id)?.status).toBe("arrived");
  expect(byId.get(completed.id)?.status).toBe("completed");

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/appointments?date=${date}&view=day`, {
    waitUntil: "domcontentloaded",
  });
  await waitForDiaryPage(page);
  await page.getByTestId("appointments-view-calendar").click();
  await switchToDayView(page);

  const sampleIds = [booked.id, arrived.id, completed.id];
  for (const appointmentId of sampleIds) {
    await expect(page.getByTestId(`appointment-event-${appointmentId}`)).toBeVisible({
      timeout: 20_000,
    });
  }

  const metrics = await page.evaluate(() => {
    const labels = Array.from(
      document.querySelectorAll(".rbc-time-gutter .rbc-label")
    )
      .map((node) => ({
        text: (node.textContent || "").trim(),
        top: node.getBoundingClientRect().top,
      }))
      .map((item) => {
        const match = /^(\d{1,2}):(\d{2})$/.exec(item.text);
        if (!match) return null;
        return {
          minutes: Number(match[1]) * 60 + Number(match[2]),
          top: item.top,
        };
      })
      .filter((item): item is { minutes: number; top: number } => Boolean(item))
      .sort((a, b) => a.minutes - b.minutes);

    if (labels.length < 2) return null;
    const first = labels[0];
    const last = labels[labels.length - 1];
    const minuteDelta = Math.max(1, last.minutes - first.minutes);
    const pxPerMinute = (last.top - first.top) / minuteDelta;
    return { anchorMinutes: first.minutes, anchorTop: first.top, pxPerMinute };
  });
  expect(metrics).not.toBeNull();

  for (const appointmentId of sampleIds) {
    const snapshotItem = byId.get(appointmentId);
    expect(snapshotItem).toBeTruthy();
    const eventCard = page.getByTestId(`appointment-event-${appointmentId}`);
    const box = await eventCard.boundingBox();
    expect(box).not.toBeNull();
    const expectedTop =
      metrics!.anchorTop +
      (minutesFromIso(snapshotItem!.starts_at) - metrics!.anchorMinutes) * metrics!.pxPerMinute;
    expect(Math.abs(box!.y - expectedTop)).toBeLessThan(24);
  }

  const statusChecks = [
    { id: booked.id, expected: "Booked" },
    { id: arrived.id, expected: "Arrived" },
    { id: completed.id, expected: "Complete" },
  ];
  const colors = new Set<string>();
  for (const item of statusChecks) {
    const pill = page.getByTestId(`appointment-event-${item.id}`).locator(".r4-status-pill");
    await expect(pill).toHaveText(item.expected);
    const bg = await pill.evaluate((el) => getComputedStyle(el as HTMLElement).backgroundColor);
    colors.add(bg);
  }
  expect(colors.size).toBeGreaterThanOrEqual(3);
});

test("diary hardening: drag/resize updates are reflected by snapshot API", async ({
  page,
  request,
}) => {
  test.setTimeout(180_000);
  const unique = Date.now();
  const date = "2026-04-15";
  const sourceRoom = `S159-From-${unique}`;
  const targetRoom = `S159-To-${unique}`;
  const baseUrl = getBaseUrl();

  const patientMove = await createPatient(request, {
    first_name: "Stage159",
    last_name: `Move ${unique}`,
  });
  const patientLane = await createPatient(request, {
    first_name: "Stage159",
    last_name: `Lane ${unique}`,
  });

  const movable = await createAppointment(request, patientMove, {
    starts_at: `${date}T10:00:00.000Z`,
    ends_at: `${date}T10:30:00.000Z`,
    location_type: "clinic",
    location: sourceRoom,
  });
  const laneTarget = await createAppointment(request, patientLane, {
    starts_at: `${date}T11:00:00.000Z`,
    ends_at: `${date}T11:30:00.000Z`,
    location_type: "clinic",
    location: targetRoom,
  });
  await setAppointmentStatus(request, laneTarget.id, "cancelled");

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/appointments?date=${date}&view=day`, {
    waitUntil: "domcontentloaded",
  });
  await waitForDiaryPage(page);
  await page.getByTestId("appointments-view-calendar").click();
  await switchToDayView(page);

  const movableEvent = page.getByTestId(`appointment-event-${movable.id}`);
  const laneEvent = page.getByTestId(`appointment-event-${laneTarget.id}`);
  await expect(movableEvent).toBeVisible({ timeout: 20_000 });
  await expect(laneEvent).toBeVisible({ timeout: 20_000 });

  await movableEvent.dragTo(laneEvent);
  await expect
    .poll(async () => {
      const snapshot = await getSnapshotForDate(request, date);
      const item = snapshot.appointments.find((appt) => appt.id === movable.id);
      return {
        starts_at: item?.starts_at ?? "",
        location: item?.location ?? "",
      };
    })
    .toEqual(
      expect.objectContaining({
        starts_at: expect.stringContaining(`${date}T11:00`),
        location: targetRoom,
      })
    );

  const resizableEvent = page
    .locator(".rbc-addons-dnd-resizable", {
      has: page.getByTestId(`appointment-event-${movable.id}`),
    })
    .first();
  await resizableEvent.hover();
  const resizeHandle = resizableEvent.locator(".rbc-addons-dnd-resize-ns-anchor").last();
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
  await page.mouse.move(handleX, handleY + slotStep * 2 + 2, { steps: 8 });
  await page.mouse.up();

  await expect
    .poll(async () => {
      const snapshot = await getSnapshotForDate(request, date);
      const item = snapshot.appointments.find((appt) => appt.id === movable.id);
      return item?.duration_minutes ?? 0;
    })
    .toBeGreaterThan(30);
});

test("diary hardening: render timing guard", async ({ page, request }) => {
  const baseUrl = getBaseUrl();
  const date = "2026-01-15";
  const budgetMs = Number(process.env.APPOINTMENTS_DIARY_RENDER_BUDGET_MS ?? "12000");
  const startedAt = Date.now();

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/appointments?date=${date}&view=day`, {
    waitUntil: "domcontentloaded",
  });
  await waitForDiaryPage(page);
  await page.getByTestId("appointments-view-calendar").click();
  await switchToDayView(page);
  await expect(page.getByTestId("appointments-diary-columns")).toBeVisible({ timeout: 20_000 });
  await expect
    .poll(async () => page.locator('[data-testid^="appointment-event-"]').count(), {
      timeout: 20_000,
    })
    .toBeGreaterThan(0);

  const elapsedMs = Date.now() - startedAt;
  console.log("DIARY_RENDER_MS", elapsedMs);
  expect(elapsedMs).toBeLessThan(budgetMs);
});
