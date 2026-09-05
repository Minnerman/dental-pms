import { expect, test, type Page } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

type Session = { start_time: string | null; end_time: string | null; is_closed: boolean };
type Schedule = {
  hours: Array<Session & { day_of_week: number }>;
  closures: Array<{ start_date: string; end_date: string; reason: string | null }>;
  overrides: Array<Session & { date: string; reason: string | null }>;
};

test.use({ timezoneId: "Europe/London" });

const testDate = "2030-01-14";
const readWriteCapabilities = ["appointments.view", "appointments.write", "patients.view"];

function weeklySchedule(split = false): Schedule {
  return {
    hours: Array.from({ length: 7 }, (_, day) => split
      ? [
        { day_of_week: day, start_time: "09:00", end_time: "12:00", is_closed: false },
        { day_of_week: day, start_time: "14:00", end_time: "17:00", is_closed: false },
      ]
      : [{ day_of_week: day, start_time: "09:00", end_time: "17:00", is_closed: false }]).flat(),
    closures: [], overrides: [],
  };
}

async function mockSchedule(page: Page, schedule = weeklySchedule()) {
  await page.route("**/api/settings/schedule", (route) => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify(schedule),
  }));
}

async function mockCapabilities(page: Page, capabilities = readWriteCapabilities) {
  await page.route("**/api/me/capabilities", (route) => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify(capabilities),
  }));
}

async function openCalendar(page: Page, date = testDate) {
  await page.goto(`${getBaseUrl()}/appointments?date=${date}&view=day`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("appointments-page")).toBeVisible({ timeout: 20_000 });
  await page.getByTestId("appointments-view-calendar").click();
  await page.getByTestId("appointments-calendar-view-day").click();
}

async function openBooking(page: Page, patientId: string, start = `${testDate}T09:00`, duration = 30) {
  await page.goto(`${getBaseUrl()}/appointments?patientId=${patientId}&book=1&start=${start}&duration=${duration}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("booking-start")).toHaveValue(start);
}

test("right-clicking an empty calendar slot starts booking at that exact date and time", async ({ page, request }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await primePageAuth(page, request);
  await mockSchedule(page);
  await mockCapabilities(page);
  await page.route("**/api/appointments/range?*", (route) => route.fulfill({ status: 200, contentType: "application/json", body: "[]" }));
  await openCalendar(page);
  await page.screenshot({ path: testInfo.outputPath("schedule-day-light.png"), fullPage: true });
  const slot = page.locator(`.rbc-day-slot [data-testid^="schedule-slot-${testDate}-10-00"]`).first();
  await expect(slot).toBeVisible();
  await slot.click({ button: "right" });
  await expect(page.getByTestId("booking-modal")).toBeVisible();
  await expect(page.getByTestId("booking-start")).toHaveValue(`${testDate}T10:00`);
  await expect(page.getByTestId("booking-end")).toHaveValue(`${testDate}T10:30`);
  await page.screenshot({ path: testInfo.outputPath("schedule-booking-light.png") });
  await page.setViewportSize({ width: 390, height: 844 });
  const modal = page.getByTestId("booking-modal");
  await expect.poll(() => modal.evaluate((element) => {
    const box = element.getBoundingClientRect();
    return box.left >= 0 && box.right <= window.innerWidth + 1 && element.scrollWidth <= element.clientWidth + 1;
  })).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("schedule-booking-mobile.png") });
  await modal.getByRole("button", { name: "Close", exact: true }).click();
  await expect(modal).toHaveCount(0);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("button", { name: "Toggle theme", exact: true }).click();
  await page.getByTestId("appointments-calendar-view-week").click();
  await expect(page.locator(".rbc-time-header-content .rbc-header")).toHaveCount(7);
  await page.screenshot({ path: testInfo.outputPath("schedule-week-dark.png"), fullPage: true });
});

test("long appointment durations preserve exact minute lengths including three hours ten minutes", async ({ page, request }) => {
  const patientId = await createPatient(request, { first_name: "Synthetic Duration", last_name: `Schedule${Date.now()}` });
  await primePageAuth(page, request);
  await mockSchedule(page);
  await openBooking(page, patientId);
  const duration = page.getByTestId("booking-duration");
  for (const [minutes, end] of [[180, "12:00"], [190, "12:10"], [210, "12:30"], [240, "13:00"], [300, "14:00"], [360, "15:00"]] as const) {
    await duration.selectOption(String(minutes));
    await expect(page.getByTestId("booking-end")).toHaveValue(`${testDate}T${end}`);
    await expect(duration).toHaveValue(String(minutes));
  }
  await page.getByTestId("duration-preset-240").click();
  await expect(page.getByTestId("booking-end")).toHaveValue(`${testDate}T13:00`);
  await page.getByTestId("booking-end").fill(`${testDate}T12:10`);
  await expect(duration).toHaveValue("190");
});

test("outside-hours booking remains allowed and the saved calendar appointment has a red warning edge", async ({ page, request }, testInfo) => {
  const unique = Date.now();
  const patientId = await createPatient(request, { first_name: "Synthetic Late", last_name: `Schedule${unique}` });
  await primePageAuth(page, request);
  await mockSchedule(page);
  await openBooking(page, patientId, `${testDate}T20:00`, 180);
  await page.getByTestId("booking-location-room").fill(`Synthetic late room ${unique}`);
  await expect(page.getByTestId("booking-outside-hours-warning")).toBeVisible();
  await expect(page.getByTestId("booking-submit")).toBeEnabled();
  const saved = page.waitForResponse((response) => new URL(response.url()).pathname === "/api/appointments" && response.request().method() === "POST");
  await page.getByTestId("booking-submit").click();
  const response = await saved;
  expect(response.ok()).toBeTruthy();
  const appointment = await response.json();
  expect(new Date(appointment.ends_at).getTime() - new Date(appointment.starts_at).getTime()).toBe(180 * 60_000);
  await openCalendar(page);
  await page.getByTestId("appointments-show-full-day").check();
  const event = page.getByTestId(`appointment-event-${appointment.id}`);
  await expect(event).toHaveAttribute("data-outside-hours", "true");
  await event.scrollIntoViewIfNeeded();
  await expect(event).toBeVisible();
  const eventBlock = event.locator("xpath=ancestor::*[contains(concat(' ', normalize-space(@class), ' '), ' rbc-event ')][1]");
  await expect(eventBlock).toHaveCSS("border-left-width", "4px");
  expect(await eventBlock.evaluate((element) => (element as HTMLElement).style.borderLeft.includes("var(--danger)"))).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("schedule-outside-hours.png"), fullPage: true });
  await page.getByRole("button", { name: "Toggle theme", exact: true }).click();
  await page.screenshot({ path: testInfo.outputPath("schedule-outside-hours-dark.png"), fullPage: true });
});

test("split sessions and one-off full and half-day closures produce accurate advisory warnings", async ({ page, request }) => {
  const patientId = await createPatient(request, { first_name: "Synthetic Closure", last_name: `Schedule${Date.now()}` });
  await primePageAuth(page, request);
  const schedule = weeklySchedule(true);
  schedule.closures = [{ start_date: "2030-01-15", end_date: "2030-01-16", reason: "Synthetic closure" }];
  schedule.overrides = [
    { date: "2030-01-16", start_time: "14:00", end_time: "17:00", is_closed: false, reason: "Synthetic afternoon only" },
    { date: "2030-01-17", start_time: null, end_time: null, is_closed: true, reason: "Synthetic full day" },
  ];
  await mockSchedule(page, schedule);
  await openBooking(page, patientId, `${testDate}T12:15`, 30);
  const warning = page.getByTestId("booking-outside-hours-warning");
  await expect(warning).toBeVisible();
  for (const [start, end, outside] of [
    ["2030-01-14T14:00", "2030-01-14T14:30", false],
    ["2030-01-14T11:45", "2030-01-14T14:15", true],
    ["2030-01-15T10:00", "2030-01-15T10:30", true],
    ["2030-01-16T10:00", "2030-01-16T10:30", true],
    ["2030-01-16T14:00", "2030-01-16T14:30", false],
    ["2030-01-17T10:00", "2030-01-17T10:30", true],
  ] as const) {
    await page.getByTestId("booking-start").fill(start);
    await page.getByTestId("booking-end").fill(end);
    if (outside) await expect(warning).toBeVisible();
    else await expect(warning).toHaveCount(0);
  }
});

test("view-only appointments cannot open a booking from a blank slot", async ({ page, request }) => {
  await primePageAuth(page, request);
  await mockSchedule(page);
  await mockCapabilities(page, ["appointments.view"]);
  await page.route("**/api/appointments/range?*", (route) => route.fulfill({ status: 200, contentType: "application/json", body: "[]" }));
  await openCalendar(page);
  const slot = page.locator(`.rbc-day-slot [data-testid^="schedule-slot-${testDate}-10-00"]`).first();
  await expect(slot).toBeVisible();
  await slot.click({ button: "right" });
  await expect(page.getByTestId("booking-modal")).toHaveCount(0);
  await expect(page.getByTestId("new-appointment")).toHaveCount(0);
});

test("unavailable opening hours are explicitly unknown rather than silently marked in-hours", async ({ page, request }) => {
  const patientId = await createPatient(request, { first_name: "Synthetic Unknown", last_name: `Schedule${Date.now()}` });
  await primePageAuth(page, request);
  await page.route("**/api/settings/schedule", (route) => route.fulfill({ status: 503, contentType: "text/html", body: "<html>private schedule response</html>" }));
  await openBooking(page, patientId);
  await expect(page.getByTestId("booking-schedule-error")).toBeVisible();
  await expect(page.getByTestId("booking-outside-hours-warning")).toHaveCount(0);
  await expect(page.getByTestId("booking-modal")).not.toContainText("private schedule response");
  await expect(page.getByTestId("booking-submit")).toBeEnabled();
});

test("right-clicking an unassigned clinician lane clears the clinician from a previously closed booking", async ({ page, request }) => {
  await primePageAuth(page, request);
  await mockSchedule(page);
  await mockCapabilities(page);
  await page.route("**/api/users", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([{ id: 98002, email: "synthetic.dentist@example.test", full_name: "Synthetic dentist", role: "dentist", is_active: true }]) }));
  await page.route("**/api/appointments/range?*", (route) => route.fulfill({ status: 200, contentType: "application/json", body: "[]" }));
  await openCalendar(page);
  await page.getByTestId("appointments-diary-grouping").selectOption("clinician");
  const slot = page.getByTestId(`schedule-slot-${testDate}-10-00-clinician:unassigned`);
  await slot.click({ button: "right" });
  const modal = page.getByTestId("booking-modal");
  const clinician = modal.locator("#booking-clinician");
  await clinician.selectOption("98002");
  await expect(clinician).toHaveValue("98002");
  await modal.getByRole("button", { name: "Close", exact: true }).click();
  await slot.click({ button: "right" });
  await expect(clinician).toHaveValue("");
});

test("Escape during an in-flight booking cannot dismiss the dialog or navigate the background diary", async ({ page, request }) => {
  const unique = Date.now();
  const patientId = await createPatient(request, { first_name: "Synthetic Pending", last_name: `Schedule${unique}` });
  await primePageAuth(page, request);
  await mockSchedule(page);
  await openBooking(page, patientId);
  await page.getByTestId("booking-location-room").fill(`Synthetic pending room ${unique}`);
  let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  let seen!: () => void;
  const requested = new Promise<void>((resolve) => { seen = resolve; });
  let writes = 0;
  await page.route("**/api/appointments", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    writes += 1;
    seen();
    await gate;
    await route.continue();
  });
  try {
    await page.getByTestId("booking-submit").click();
    await requested;
    const modal = page.getByTestId("booking-modal");
    const bookingUrl = page.url();
    await expect(page.getByTestId("booking-submit")).toBeDisabled();
    await page.keyboard.press("Escape");
    await expect(modal).toBeVisible();
    await page.keyboard.press("PageDown");
    expect(page.url()).toBe(bookingUrl);
    expect(writes).toBe(1);
    release();
    await expect(modal).toHaveCount(0, { timeout: 20_000 });
  } finally {
    release();
  }
});

async function openSettings(page: Page) {
  await page.goto(`${getBaseUrl()}/settings/schedule`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("schedule-settings")).toBeVisible({ timeout: 20_000 });
}

async function saveSettings(page: Page) {
  const saved = page.waitForResponse((response) => new URL(response.url()).pathname === "/api/settings/schedule" && response.request().method() === "PUT");
  await page.getByRole("button", { name: "Save schedule", exact: true }).last().click();
  expect((await saved).ok()).toBeTruthy();
  await expect(page.getByRole("status").filter({ hasText: "Schedule saved. Existing appointments have not been changed or cancelled." })).toBeVisible();
}

test("seven-day split opening sessions save to the real API and survive reload", async ({ page, request }, testInfo) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  const token = await primePageAuth(page, request);
  const headers = { Authorization: `Bearer ${token}` };
  const endpoint = `${getBaseUrl()}/api/settings/schedule`;
  const previous = await request.get(endpoint, { headers });
  expect(previous.ok()).toBeTruthy();
  const snapshot = await previous.json();
  try {
    expect((await request.put(endpoint, { headers, data: weeklySchedule() })).ok()).toBeTruthy();
    await openSettings(page);
    await expect(page.getByTestId("schedule-settings")).toHaveAttribute("data-mode", "edit");
    const weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
    for (let day = 0; day < weekdays.length; day += 1) {
      await expect(page.getByTestId(`weekly-day-${day}`)).toBeVisible();
      await expect(page.getByLabel(`${weekdays[day]} session 1 start`, { exact: true })).toHaveValue("09:00");
    }
    await page.getByLabel("Monday session 1 end", { exact: true }).fill("12:00");
    await page.getByRole("button", { name: /Add session.*for Monday$/ }).click();
    await page.getByLabel("Monday session 2 start", { exact: true }).fill("14:00");
    await page.getByLabel("Monday session 2 end", { exact: true }).fill("17:00");
    await page.getByLabel("Saturday session 1 start", { exact: true }).fill("10:00");
    await page.getByLabel("Sunday closed", { exact: true }).check();
    await saveSettings(page);
    const persisted = await request.get(endpoint, { headers });
    expect(persisted.ok()).toBeTruthy();
    const data = await persisted.json();
    expect(data.hours.filter((row: { day_of_week: number }) => row.day_of_week === 0).map((row: Session) => [row.start_time?.slice(0, 5), row.end_time?.slice(0, 5)])).toEqual([["09:00", "12:00"], ["14:00", "17:00"]]);
    expect(data.hours.find((row: { day_of_week: number }) => row.day_of_week === 6).is_closed).toBe(true);
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByLabel("Monday session 2 start", { exact: true })).toHaveValue("14:00");
    await expect(page.getByLabel("Saturday session 1 start", { exact: true })).toHaveValue("10:00");
    await expect(page.getByLabel("Sunday closed", { exact: true })).toBeChecked();
    await page.screenshot({ path: testInfo.outputPath("schedule-weekly-sessions.png"), fullPage: true });
    await page.getByRole("button", { name: "Toggle theme", exact: true }).click();
    await page.setViewportSize({ width: 390, height: 844 });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    await page.getByTestId("weekly-day-0").scrollIntoViewIfNeeded();
    await page.screenshot({ path: testInfo.outputPath("schedule-weekly-mobile-dark.png") });
  } finally {
    expect((await request.put(endpoint, { headers, data: snapshot })).ok()).toBeTruthy();
  }
});

test("the closure calendar persists a whole closed day and an afternoon-only half day", async ({ page, request }, testInfo) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  const token = await primePageAuth(page, request);
  const headers = { Authorization: `Bearer ${token}` };
  const endpoint = `${getBaseUrl()}/api/settings/schedule`;
  const previous = await request.get(endpoint, { headers });
  expect(previous.ok()).toBeTruthy();
  const snapshot = await previous.json();
  try {
    expect((await request.put(endpoint, { headers, data: weeklySchedule() })).ok()).toBeTruthy();
    await openSettings(page);
    const month = await page.evaluate(() => {
      const parts = Object.fromEntries(new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/London", year: "numeric", month: "2-digit" }).formatToParts(new Date()).map((part) => [part.type, part.value]));
      return `${parts.year}-${parts.month}`;
    });
    const wholeDay = `${month}-14`;
    const halfDay = `${month}-15`;
    await page.getByTestId(`closure-date-${wholeDay}`).click();
    await page.getByLabel("Date opening arrangement", { exact: true }).selectOption("closed");
    await page.getByRole("button", { name: "Apply date to draft", exact: true }).click();
    await page.getByTestId(`closure-date-${halfDay}`).click();
    await page.getByLabel("Date opening arrangement", { exact: true }).selectOption("morning");
    await page.getByLabel("Half-day boundary", { exact: true }).fill("13:00");
    await page.getByRole("button", { name: "Apply date to draft", exact: true }).click();
    await saveSettings(page);
    const persisted = await request.get(endpoint, { headers });
    expect(persisted.ok()).toBeTruthy();
    const data = await persisted.json();
    expect(data.overrides.find((row: { date: string }) => row.date === wholeDay).is_closed).toBe(true);
    const afternoon = data.overrides.filter((row: { date: string }) => row.date === halfDay);
    expect(afternoon).toHaveLength(1);
    expect(afternoon[0].start_time.slice(0, 5)).toBe("13:00");
    expect(afternoon[0].end_time.slice(0, 5)).toBe("17:00");
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.getByTestId(`closure-date-${wholeDay}`).click();
    await expect(page.getByLabel("Date opening arrangement", { exact: true })).toHaveValue("closed");
    await page.getByTestId(`closure-date-${halfDay}`).click();
    await expect(page.getByLabel("Selected date session 1 start", { exact: true })).toHaveValue("13:00");
    await expect(page.getByLabel("Selected date session 1 end", { exact: true })).toHaveValue("17:00");
    await page.screenshot({ path: testInfo.outputPath("schedule-closure-calendar.png"), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    await page.getByTestId("closure-calendar").scrollIntoViewIfNeeded();
    await page.screenshot({ path: testInfo.outputPath("schedule-closure-mobile.png") });
  } finally {
    expect((await request.put(endpoint, { headers, data: snapshot })).ok()).toBeTruthy();
  }
});

test("non-admin users can inspect hours but cannot change or save practice settings", async ({ page, request }) => {
  await primePageAuth(page, request);
  await mockSchedule(page);
  await mockCapabilities(page, ["appointments.view"]);
  await page.route("**/api/me", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id: 98001, email: "synthetic.viewer@example.test", full_name: "Synthetic viewer", role: "reception", is_active: true, must_change_password: false }) }));
  await openSettings(page);
  await expect(page.getByTestId("schedule-settings")).toHaveAttribute("data-mode", "read-only");
  await expect(page.getByTestId("schedule-read-only")).toBeVisible();
  await expect(page.getByLabel("Monday session 1 start", { exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: /Add session.*for Monday$/ })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Save schedule", exact: true })).toHaveCount(0);
});

test("unverified settings access never exposes an editable schedule", async ({ page, request }) => {
  await primePageAuth(page, request);
  await mockSchedule(page);
  await page.route("**/api/me", (route) => route.fulfill({ status: 503, contentType: "text/html", body: "<html>private operator details</html>" }));
  await page.goto(`${getBaseUrl()}/settings/schedule`, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Session unavailable", exact: true })).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "We could not verify your session." })).toBeVisible();
  await expect(page.getByTestId("schedule-settings")).toHaveCount(0);
  await expect(page.getByTestId("weekly-day-0")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Save schedule", exact: true })).toHaveCount(0);
  await expect(page.locator("body")).not.toContainText("private operator details");
});

test("a failed settings save keeps the draft and never reports success", async ({ page, request }) => {
  await primePageAuth(page, request);
  await page.route("**/api/settings/schedule", (route) => route.fulfill(route.request().method() === "PUT"
    ? { status: 503, contentType: "text/html", body: "<html>private settings failure details</html>" }
    : { status: 200, contentType: "application/json", body: JSON.stringify(weeklySchedule()) }));
  await openSettings(page);
  await page.getByLabel("Monday session 1 start", { exact: true }).fill("09:15");
  await page.getByRole("button", { name: "Save schedule", exact: true }).last().click();
  await expect(page.getByTestId("schedule-settings").getByRole("alert")).toBeVisible();
  await expect(page.getByLabel("Monday session 1 start", { exact: true })).toHaveValue("09:15");
  await expect(page.getByRole("status").filter({ hasText: "Schedule saved." })).toHaveCount(0);
  await expect(page.getByTestId("schedule-settings")).not.toContainText("private settings failure details");
});
