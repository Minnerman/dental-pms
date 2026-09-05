import { expect, test, type Locator, type Page } from "@playwright/test";

import { getBaseUrl, primePageAuth } from "./helpers/auth";

const weekStart = "2030-01-14";
const sampleNames = ["One", "Two", "Three", "Four", "Five"];
const patients = sampleNames.map((name, index) => ({
  id: 97001 + index, first_name: "Sample", last_name: `Patient ${name}`,
  phone: null, email: null, date_of_birth: null, patient_category: "CLINIC_PRIVATE",
  care_setting: "CLINIC", visit_address_text: null,
}));
const actor = { id: 98010, full_name: "Sample Clinician", email: "sample.clinician@example.test" };
const slots = [
  { date: "2030-01-14", start: "09:00", end: "09:40", type: "Examination", visit: false },
  { date: "2030-01-14", start: "10:30", end: "11:15", type: "Review", visit: false },
  { date: "2030-01-14", start: "13:00", end: "13:40", type: "Emergency", visit: false },
  { date: "2030-01-15", start: "14:00", end: "15:00", type: "Home visit", visit: true },
  { date: "2030-01-19", start: "10:00", end: "10:45", type: "Hygiene", visit: false },
];
const appointments = slots.map((slot, index) => ({
  id: 97501 + index, patient: patients[index], patient_has_alerts: false,
  clinician_user_id: actor.id, clinician: actor.full_name,
  starts_at: `${slot.date}T${slot.start}:00Z`, ends_at: `${slot.date}T${slot.end}:00Z`,
  status: "booked", appointment_type: slot.type,
  location_type: slot.visit ? "visit" : "clinic", location: slot.visit ? null : "Training room",
  location_text: slot.visit ? "Sample home visit" : "", is_domiciliary: slot.visit,
  visit_address: null, note_preview: null, cancel_reason: null, cancelled_at: null,
  cancelled_by_user_id: null, created_at: "2030-01-01T09:00:00Z", updated_at: "2030-01-01T09:00:00Z",
  created_by: actor, updated_by: actor, deleted_at: null, deleted_by: null,
}));
const schedule = {
  hours: [
    ...Array.from({ length: 5 }, (_, day) => [
      { day_of_week: day, start_time: "09:00", end_time: "13:00", is_closed: false },
      { day_of_week: day, start_time: "14:00", end_time: "17:00", is_closed: false },
    ]).flat(),
    { day_of_week: 5, start_time: "09:00", end_time: "13:00", is_closed: false },
    { day_of_week: 6, start_time: null, end_time: null, is_closed: true },
  ],
  closures: [], overrides: [],
};

test.use({ timezoneId: "Europe/London", viewport: { width: 1440, height: 1050 } });

async function scrollWeekToNine(page: Page) {
  const slot = page.locator(`.rbc-day-slot [data-testid^="schedule-slot-${weekStart}-09-00"]`).first();
  await expect(slot).toBeVisible();
  await slot.evaluate((element) => {
    const scroller = element.closest(".rbc-time-content");
    if (!scroller) throw new Error("Calendar scroll area not found");
    scroller.scrollTop += element.getBoundingClientRect().top - scroller.getBoundingClientRect().top - 1;
  });
}

async function expectReadableToolbarButton(button: Locator) {
  await expect(button).toBeEnabled();
  const ratio = await button.evaluate((element) => {
    const rgb = (value: string) => {
      const values = value.match(/[\d.]+/g)?.map(Number) ?? [];
      return values.length >= 3 ? values : [0, 0, 0, 0];
    };
    const foreground = rgb(getComputedStyle(element).color);
    let background = [255, 255, 255];
    let ancestor: Element | null = element;
    while (ancestor) {
      const candidate = rgb(getComputedStyle(ancestor).backgroundColor);
      if (candidate.length < 4 || candidate[3] > 0.99) { background = candidate; break; }
      ancestor = ancestor.parentElement;
    }
    const luminance = (channels: number[]) => channels.slice(0, 3).reduce((total, channel, index) => {
      const normal = channel / 255;
      const linear = normal <= 0.04045 ? normal / 12.92 : ((normal + 0.055) / 1.055) ** 2.4;
      return total + linear * [0.2126, 0.7152, 0.0722][index];
    }, 0);
    const first = luminance(foreground), second = luminance(background);
    return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
  });
  expect(ratio).toBeGreaterThanOrEqual(4.5);
}

test("synthetic schedule preview shows sample bookings, closed sessions and readable light and dark controls", async ({ page, request }, testInfo) => {
  await primePageAuth(page, request);
  await page.route("**/api/me", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...actor, role: "superadmin", is_active: true, must_change_password: false }) }));
  await page.route("**/api/me/capabilities", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(["appointments.view", "appointments.write", "patients.view"]) }));
  await page.route("**/api/users", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([{ ...actor, role: "dentist", is_active: true }]) }));
  await page.route("**/api/patients?*", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(patients) }));
  await page.route("**/api/appointments/range?*", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(appointments) }));
  await page.route("**/api/settings/schedule", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(schedule) }));
  let writes = 0;
  await page.route("**/api/appointments", (route) => {
    if (route.request().method() === "POST") writes += 1;
    return route.fulfill({ status: 405, contentType: "application/json", body: JSON.stringify({ detail: "Read-only synthetic preview" }) });
  });

  await page.goto(`${getBaseUrl()}/appointments?date=${weekStart}&view=week`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("appointments-page")).toBeVisible({ timeout: 20_000 });
  await page.getByTestId("appointments-view-calendar").click();
  await page.getByTestId("appointments-calendar-view-week").click();
  await expect(page.locator('[data-testid^="appointment-event-"]')).toHaveCount(5);
  await expect(page.getByTestId("appointment-event-97503")).toHaveAttribute("data-outside-hours", "true");
  await expect(page.getByTestId("appointment-event-97501")).toHaveAttribute("data-outside-hours", "false");
  for (const [date, time, outside] of [
    ["2030-01-14", "10-00", "false"],
    ["2030-01-14", "13-00", "true"],
    ["2030-01-19", "14-00", "true"],
    ["2030-01-20", "10-00", "true"],
  ]) {
    await expect(page.locator(`.rbc-day-slot [data-testid^="schedule-slot-${date}-${time}"]`).first()).toHaveAttribute("data-outside-hours", outside);
  }
  await scrollWeekToNine(page);
  await expectReadableToolbarButton(page.getByTestId("appointments-calendar-next"));
  await expectReadableToolbarButton(page.getByTestId("appointments-calendar-view-day"));
  await page.screenshot({ path: testInfo.outputPath("schedule-preview-week-light.png"), fullPage: true });
  await page.getByRole("button", { name: "Toggle theme", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expectReadableToolbarButton(page.getByTestId("appointments-calendar-next"));
  await expectReadableToolbarButton(page.getByTestId("appointments-calendar-view-day"));
  await scrollWeekToNine(page);
  await page.screenshot({ path: testInfo.outputPath("schedule-preview-week-dark.png"), fullPage: true });

  await page.getByRole("button", { name: "Toggle theme", exact: true }).click();
  const blankSlot = page.locator(`.rbc-day-slot [data-testid^="schedule-slot-${weekStart}-11-40"]`).first();
  await blankSlot.click({ button: "right" });
  await expect(page.getByTestId("booking-modal")).toBeVisible();
  await expect(page.getByTestId("booking-start")).toHaveValue(`${weekStart}T11:40`);
  await expect(page.getByTestId("booking-end")).toHaveValue(`${weekStart}T12:10`);
  await page.getByTestId("booking-patient-select").selectOption("97001");
  await expect(page.getByTestId("booking-error")).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("schedule-preview-booking-light.png") });
  expect(writes).toBe(0);
});
