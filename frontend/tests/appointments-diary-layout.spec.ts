import { expect, test } from "@playwright/test";

import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

type SnapshotAppointment = {
  id: number;
  location?: string | null;
  location_type: "clinic" | "visit";
};

type DiarySnapshot = {
  appointments: SnapshotAppointment[];
};

function toChairLabel(item: SnapshotAppointment) {
  const location = (item.location || "").trim();
  if (location) return location;
  return item.location_type === "visit" ? "Visit" : "Unassigned";
}

async function switchToDayView(page: any) {
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

test("diary day columns and appointment blocks align with snapshot API", async ({
  page,
  request,
}) => {
  const date = "2026-02-04";
  const token = await ensureAuthReady(request);
  const baseUrl = getBaseUrl();
  const snapshotResponse = await request.get(
    `${baseUrl}/api/appointments/snapshot?date=${date}&view=day&mask_names=true`,
    {
      headers: { Authorization: `Bearer ${token}` },
    }
  );
  expect(snapshotResponse.ok()).toBeTruthy();
  const snapshot = (await snapshotResponse.json()) as DiarySnapshot;
  test.skip(
    snapshot.appointments.length === 0,
    `No appointments found for snapshot date ${date}.`
  );

  const expectedBlocks = snapshot.appointments.length;
  const expectedColumns = Math.max(
    1,
    new Set(snapshot.appointments.map((item) => toChairLabel(item))).size
  );

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/appointments?date=${date}&view=day`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("appointments-page")).toBeVisible({ timeout: 15_000 });
  await page.getByTestId("appointments-view-calendar").click();
  await switchToDayView(page);

  await expect(page.getByTestId("appointments-diary-grouping")).toHaveValue("chair");
  await expect(page.getByTestId("appointments-diary-columns")).toBeVisible();
  await expect(page.locator('[data-testid^="appointments-diary-column-"]')).toHaveCount(
    expectedColumns
  );
  await expect
    .poll(() => page.locator('[data-testid^="appointment-event-"]').count(), {
      timeout: 15_000,
    })
    .toBe(expectedBlocks);
});
