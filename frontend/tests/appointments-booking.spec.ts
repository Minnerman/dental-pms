import { expect, test } from "@playwright/test";
import { createAppointment, createPatient } from "./helpers/api";
import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

async function openAppointments(page: any, request: any, url: string) {
  await primePageAuth(page, request);
  await page.goto(url, { waitUntil: "domcontentloaded" });
  await expect(page).toHaveURL(/\/appointments/);
  await expect(page).not.toHaveURL(/\/change-password|\/login/);
  await expect(page.getByTestId("appointments-page")).toBeVisible({ timeout: 15_000 });
  await page
    .getByTestId("new-appointment")
    .waitFor({ state: "visible", timeout: 30_000 })
    .catch(() => {});
}

async function clickNewAppointment(page: any) {
  const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      if (page.isClosed?.()) throw new Error("Page closed before clickNewAppointment");
      const button = page.getByTestId("new-appointment");
      await button.waitFor({ state: "visible", timeout: 30_000 });
      await button.click({ timeout: 30_000 });
      await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 30_000 });
      return;
    } catch (error) {
      if (attempt === 3) throw error;
      if (page.isClosed?.()) throw error;
      await sleep(250);
    }
  }
}

async function createConflictAppointment(
  request: any,
  patientId: string,
  clinicianId: number,
  startsAt: string,
  endsAt: string
) {
  const token = await ensureAuthReady(request);
  const baseURL = getBaseUrl();
  const response = await request.post(`${baseURL}/api/appointments`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      patient_id: Number(patientId),
      clinician_user_id: clinicianId,
      starts_at: startsAt,
      ends_at: endsAt,
      status: "booked",
      location_type: "clinic",
      location: "Room 1",
      location_text: "",
    },
  });
  expect(response.ok()).toBeTruthy();
}

async function selectBookingPatient(page: any, patientId: string, searchTerm: string) {
  const search = page.getByTestId("booking-patient-search");
  const select = page.getByTestId("booking-patient-select");
  const searchResponse = page
    .waitForResponse(
      (response: any) =>
        response.url().includes("/api/patients?") &&
        response.url().includes("q=") &&
        response.request().method() === "GET" &&
        response.status() === 200,
      { timeout: 15_000 }
    )
    .catch(() => null);
  await search.fill("");
  await search.pressSequentially(searchTerm, { delay: 20 });
  await expect(search).toHaveValue(searchTerm);
  await searchResponse;
  await expect(select.locator(`option[value="${patientId}"]`)).toHaveCount(1, {
    timeout: 15_000,
  });
  await select.selectOption(String(patientId));
  await expect(select).toHaveValue(String(patientId));
}
test("appointments deep link opens modal and cleans URL", async ({ page, request }) => {
  await openAppointments(page, request, "/appointments?date=2026-01-15&book=1");
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 15_000 });
  await page.waitForURL((url) => !url.searchParams.has("book"), { timeout: 15_000 });
});

test("appointments refresh after deep link does not reopen without book param", async ({
  page,
  request,
}) => {
  await openAppointments(page, request, "/appointments?date=2026-01-15&book=1");
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 15_000 });
  await page.waitForURL((url) => !url.searchParams.has("book"), { timeout: 15_000 });

  await page.reload({ waitUntil: "domcontentloaded" });
  await openAppointments(page, request, page.url());
  await expect(page.getByTestId("booking-modal")).toHaveCount(0);
});

test("appointments navigation back/forward keeps modal state consistent", async ({
  page,
  request,
}) => {
  await openAppointments(page, request, "/appointments?date=2026-01-15&book=1");
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 15_000 });
  await page.waitForURL((url) => !url.searchParams.has("book"), { timeout: 15_000 });

  await openAppointments(page, request, "/appointments?date=2026-01-16");
  await page.goBack({ waitUntil: "domcontentloaded" });
  await openAppointments(page, request, page.url());
  const backUrl = new URL(page.url());
  if (backUrl.searchParams.has("book")) {
    await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 15_000 });
  } else {
    await expect(page.getByTestId("booking-modal")).toHaveCount(0);
  }
});

test("appointments modal survives view and location switches", async ({ page, request }) => {
  await openAppointments(page, request, "/appointments?date=2026-01-15");
  await clickNewAppointment(page);
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 10_000 });

  await page.getByTestId("appointments-view-calendar").click();
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 10_000 });
  await page.getByTestId("appointments-view-day-sheet").click();
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 10_000 });

  await page.getByLabel("Jump to").fill("2026-01-16");
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 10_000 });

  const clinicianSelect = page.getByLabel("Clinician (optional)");
  const clinicianOptions = await clinicianSelect
    .locator("option")
    .evaluateAll((options) =>
      options
        .map((option) => (option as HTMLOptionElement).value)
        .filter(Boolean)
    );
  if (clinicianOptions.length > 0) {
    await clinicianSelect.selectOption(clinicianOptions[0]);
  }
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 10_000 });

  await page.getByTestId("booking-location-type").selectOption("visit");
  const roomInput = page.getByTestId("booking-location-room");
  await expect(roomInput).toBeDisabled({ timeout: 15_000 });
  await expect(page.getByTestId("booking-visit-address")).toBeVisible({ timeout: 15_000 });
  await page.getByTestId("booking-visit-address").fill("123 Test Street");
  await page.getByTestId("booking-location-type").selectOption("clinic");
  await expect(roomInput).toBeEnabled({ timeout: 15_000 });
  await roomInput.fill("Room 1");
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 10_000 });
});

test("appointments shortcuts open, focus, and close booking", async ({ page, request }) => {
  await openAppointments(page, request, "/appointments?date=2026-01-15");

  const globalSearch = page.getByPlaceholder("Search patients...");
  await page.keyboard.press("Slash");
  await expect(globalSearch).toBeFocused();

  await page.locator("body").click();
  await page.keyboard.press("n");
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("booking-patient-search")).toBeFocused();

  await page.locator("body").click();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("booking-modal")).toBeHidden({ timeout: 10_000 });
});

test("appointment creation uses latest clinician and location selections", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);
  const unique = Date.now();
  const lastName = `Patient ${unique}`;
  const patientId = await createPatient(request, {
    first_name: "Test",
    last_name: lastName,
  });
  await openAppointments(page, request, "/appointments?date=2026-01-15");
  await clickNewAppointment(page);
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 10_000 });

  await selectBookingPatient(page, patientId, lastName);

  const start = page.getByTestId("booking-start");
  await expect(start).toBeVisible({ timeout: 60_000 });
  await start.fill("2026-01-15T09:00");

  const end = page.getByTestId("booking-end");
  await expect(end).toBeVisible({ timeout: 60_000 });
  await end.fill("2026-01-15T09:30");

  const clinicianSelect = page.getByLabel("Clinician (optional)");
  const clinicianOptions = await clinicianSelect
    .locator("option")
    .evaluateAll((options) =>
      options
        .map((option) => (option as HTMLOptionElement).value)
        .filter(Boolean)
    );
  let expectedClinician = "";
  if (clinicianOptions.length >= 2) {
    await clinicianSelect.selectOption(clinicianOptions[0]);
    await clinicianSelect.selectOption(clinicianOptions[1]);
    expectedClinician = clinicianOptions[1];
  } else if (clinicianOptions.length === 1) {
    await clinicianSelect.selectOption(clinicianOptions[0]);
    expectedClinician = clinicianOptions[0];
  }

  const roomInput = page.getByTestId("booking-location-room");
  await roomInput.fill("Room 1");
  await roomInput.fill("Room 2");

  const locationType = page.getByTestId("booking-location-type");
  await locationType.selectOption("visit");
  await page.getByTestId("booking-visit-address").fill("123 Test Street");
  await locationType.selectOption("clinic");

  const requestPromise = page.waitForRequest((req) => {
    if (req.method() !== "POST") return false;
    return new URL(req.url()).pathname.endsWith("/api/appointments");
  });

  await page.getByTestId("booking-submit").click();
  const req = await requestPromise;
  const payload = req.postDataJSON() as Record<string, unknown>;

  if (expectedClinician) {
    expect(payload.clinician_user_id).toBe(Number(expectedClinician));
  } else {
    expect(payload.clinician_user_id ?? null).toBeNull();
  }
  expect(payload.location_type).toBe("clinic");
  expect(payload.location).toBe("Room 2");
  expect((payload.location_text as string | undefined) ?? "").toBe("");
});

test("booking conflict check debounces and surfaces latest conflicts", async ({
  page,
  request,
}) => {
  const conflictLastName = `Patient ${Date.now()}`;
  const conflictPatientId = await createPatient(request, {
    first_name: "Conflict",
    last_name: conflictLastName,
  });
  const bookingLastName = `Patient ${Date.now()}`;
  const bookingPatientId = await createPatient(request, {
    first_name: "Booking",
    last_name: bookingLastName,
  });

  await openAppointments(page, request, "/appointments?date=2026-01-15");
  await clickNewAppointment(page);

  const clinicianSelect = page.getByLabel("Clinician (optional)");
  const clinicianOptions = await clinicianSelect
    .locator("option")
    .evaluateAll((options) =>
      options
        .map((option) => (option as HTMLOptionElement).value)
        .filter(Boolean)
    );
  if (clinicianOptions.length === 0) {
    test.skip();
    return;
  }
  const clinicianId = Number(clinicianOptions[0]);

  await createConflictAppointment(
    request,
    conflictPatientId,
    clinicianId,
    "2026-01-15T09:00:00.000Z",
    "2026-01-15T09:30:00.000Z"
  );

  await page.reload({ waitUntil: "domcontentloaded" });
  await openAppointments(page, request, page.url());
  await clickNewAppointment(page);
  await page.getByLabel("Clinician (optional)").selectOption(clinicianOptions[0]);

  await selectBookingPatient(page, bookingPatientId, bookingLastName);
  await page.getByTestId("booking-start").fill("2026-01-15T09:15");
  await page.getByTestId("booking-end").fill("2026-01-15T09:40");
  await page.getByTestId("booking-end").fill("2026-01-15T09:45");

  await page
    .getByTestId("booking-conflicts-loading")
    .waitFor({ state: "visible", timeout: 5000 })
    .catch(() => {});
  await expect(page.getByTestId("booking-conflicts")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("booking-conflict-row").first()).toBeVisible();
});

test("booking modal requires minimum fields before enabling submit", async ({
  page,
  request,
}) => {
  const requiredLastName = `Required ${Date.now()}`;
  const patientId = await createPatient(request, {
    first_name: "Test",
    last_name: requiredLastName,
  });
  await openAppointments(page, request, "/appointments?date=2026-01-15");
  await clickNewAppointment(page);

  const submit = page.getByTestId("booking-submit");
  await expect(submit).toBeDisabled();
  await expect(page.getByTestId("booking-error")).toBeVisible();
  await expect(page.getByTestId("booking-error-patient")).toBeVisible();

  await selectBookingPatient(page, patientId, requiredLastName);
  await page.getByTestId("booking-start").fill("2026-01-15T09:00");
  await page.getByTestId("booking-end").fill("2026-01-15T09:30");

  await expect(submit).toBeEnabled({ timeout: 15_000 });
  await expect(page.getByTestId("booking-error")).toHaveCount(0);
});

test("visit appointments require address, clinic does not", async ({ page, request }) => {
  const visitLastName = `Test ${Date.now()}`;
  const patientId = await createPatient(request, {
    first_name: "Visit",
    last_name: visitLastName,
  });
  await openAppointments(page, request, "/appointments?date=2026-01-15");
  await clickNewAppointment(page);

  await selectBookingPatient(page, patientId, visitLastName);
  await page.getByTestId("booking-start").fill("2026-01-15T10:00");
  await page.getByTestId("booking-end").fill("2026-01-15T10:30");

  const submit = page.getByTestId("booking-submit");
  await page.getByTestId("booking-location-type").selectOption("visit");
  await expect(submit).toBeDisabled();
  await page.getByTestId("booking-visit-address").fill("45 Main Street");
  await expect(submit).toBeEnabled({ timeout: 15_000 });

  await page.getByTestId("booking-location-type").selectOption("clinic");
  await expect(submit).toBeEnabled({ timeout: 15_000 });
});

test("conflict banner shows overlapping appointments with view day link", async ({
  page,
  request,
}) => {
  const conflictLastName = `Patient ${Date.now()}`;
  const conflictPatientId = await createPatient(request, {
    first_name: "Conflict",
    last_name: conflictLastName,
  });
  const bookingLastName = `Patient ${Date.now()}`;
  const bookingPatientId = await createPatient(request, {
    first_name: "Booking",
    last_name: bookingLastName,
  });

  await openAppointments(page, request, "/appointments?date=2026-01-15");
  await clickNewAppointment(page);

  const clinicianSelect = page.getByLabel("Clinician (optional)");
  const clinicianOptions = await clinicianSelect
    .locator("option")
    .evaluateAll((options) =>
      options
        .map((option) => (option as HTMLOptionElement).value)
        .filter(Boolean)
    );
  if (clinicianOptions.length === 0) {
    test.skip();
    return;
  }
  const clinicianId = Number(clinicianOptions[0]);
  await createAppointment(request, conflictPatientId, {
    clinician_user_id: clinicianId,
    starts_at: "2026-01-15T09:00:00.000Z",
    ends_at: "2026-01-15T09:30:00.000Z",
    location_type: "clinic",
    location: "Room 1",
  });

  await page.reload({ waitUntil: "domcontentloaded" });
  await openAppointments(page, request, page.url());
  await clickNewAppointment(page);
  await page.getByLabel("Clinician (optional)").selectOption(clinicianOptions[0]);

  await selectBookingPatient(page, bookingPatientId, bookingLastName);
  await page.getByTestId("booking-start").fill("2026-01-15T09:15");
  await page.getByTestId("booking-end").fill("2026-01-15T09:45");

  await expect(page.getByTestId("booking-conflicts")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("booking-conflict-row").first()).toBeVisible();
  await expect(page.getByTestId("booking-conflict-view-day")).toBeVisible();
});

test("booking submit is blocked when conflicts exist", async ({ page, request }) => {
  const conflictLastName = `Patient ${Date.now()}`;
  const conflictPatientId = await createPatient(request, {
    first_name: "Conflict",
    last_name: conflictLastName,
  });
  const bookingLastName = `Patient ${Date.now()}`;
  const bookingPatientId = await createPatient(request, {
    first_name: "Booking",
    last_name: bookingLastName,
  });

  await openAppointments(page, request, "/appointments?date=2026-01-15");
  await clickNewAppointment(page);

  const clinicianSelect = page.getByLabel("Clinician (optional)");
  const clinicianOptions = await clinicianSelect
    .locator("option")
    .evaluateAll((options) =>
      options
        .map((option) => (option as HTMLOptionElement).value)
        .filter(Boolean)
    );
  if (clinicianOptions.length === 0) {
    test.skip();
    return;
  }
  const clinicianId = Number(clinicianOptions[0]);

  await createAppointment(request, conflictPatientId, {
    clinician_user_id: clinicianId,
    starts_at: "2026-01-15T10:00:00.000Z",
    ends_at: "2026-01-15T10:30:00.000Z",
    location_type: "clinic",
    location: "Room 1",
  });

  await page.reload({ waitUntil: "domcontentloaded" });
  await openAppointments(page, request, page.url());
  await clickNewAppointment(page);
  await page.getByLabel("Clinician (optional)").selectOption(clinicianOptions[0]);

  await selectBookingPatient(page, bookingPatientId, bookingLastName);
  await page.getByTestId("booking-start").fill("2026-01-15T10:15");
  await page.getByTestId("booking-end").fill("2026-01-15T10:45");

  await expect(page.getByTestId("booking-conflicts")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("booking-submit")).toBeDisabled();
  await expect(page.getByTestId("booking-error")).toContainText(/conflict/i);
});

test("rescheduling respects conflicts and persists successful moves", async ({
  page,
  request,
}) => {
  const conflictPatientId = await createPatient(request, {
    first_name: "Reschedule",
    last_name: `Conflict ${Date.now()}`,
  });
  const reschedulePatientId = await createPatient(request, {
    first_name: "Reschedule",
    last_name: `Target ${Date.now()}`,
  });

  await openAppointments(page, request, "/appointments?date=2026-01-15");
  const clinicianSelect = page.getByLabel("Clinician (optional)");
  const clinicianOptions = await clinicianSelect
    .locator("option")
    .evaluateAll((options) =>
      options
        .map((option) => (option as HTMLOptionElement).value)
        .filter(Boolean)
    );
  if (clinicianOptions.length === 0) {
    test.skip();
    return;
  }
  const clinicianId = Number(clinicianOptions[0]);

  const conflictAppt = await createAppointment(request, conflictPatientId, {
    clinician_user_id: clinicianId,
    starts_at: "2026-01-15T10:00:00.000Z",
    ends_at: "2026-01-15T10:30:00.000Z",
    location_type: "clinic",
    location: "Room 1",
  });
  const movableAppt = await createAppointment(request, reschedulePatientId, {
    clinician_user_id: clinicianId,
    starts_at: "2026-01-15T11:00:00.000Z",
    ends_at: "2026-01-15T11:30:00.000Z",
    location_type: "clinic",
    location: "Room 1",
  });

  await page.reload({ waitUntil: "domcontentloaded" });
  await openAppointments(page, request, page.url());
  await page.getByTestId("appointments-view-calendar").click();
  await expect(page.getByTestId("appointments-page")).toBeVisible({ timeout: 15_000 });

  const conflictEvent = page.getByTestId(`appointment-event-${conflictAppt.id}`);
  const movableEvent = page.getByTestId(`appointment-event-${movableAppt.id}`);
  await expect(conflictEvent).toBeVisible({ timeout: 15_000 });
  await expect(movableEvent).toBeVisible({ timeout: 15_000 });

  page.once("dialog", (dialog) => dialog.accept());
  await movableEvent.dragTo(conflictEvent);
  await expect(page.getByText(/conflict: clinician already has/i)).toBeVisible({
    timeout: 15_000,
  });
  await expect(movableEvent).toContainText(/11:00/);

  const slots = page.locator(".rbc-time-slot");
  const slotCount = await slots.count();
  if (slotCount < 80) {
    test.skip();
    return;
  }

  page.once("dialog", (dialog) => dialog.accept());
  await movableEvent.dragTo(slots.nth(72));
  await expect(movableEvent.getByText(/Saving\.\.\./)).toBeVisible({
    timeout: 10_000,
  });

  await page.reload({ waitUntil: "domcontentloaded" });
  await openAppointments(page, request, page.url());
  await page.getByTestId("appointments-view-calendar").click();
  await expect(page.getByTestId(`appointment-event-${movableAppt.id}`)).toBeVisible({
    timeout: 15_000,
  });
});

test("appointment last updated metadata changes after edit", async ({ page, request }) => {
  const patientId = await createPatient(request, {
    first_name: "Audit",
    last_name: `Meta ${Date.now()}`,
  });
  const appointment = await createAppointment(request, patientId, {
    clinician_user_id: null,
    starts_at: "2026-01-15T12:00:00.000Z",
    ends_at: "2026-01-15T12:30:00.000Z",
    location_type: "clinic",
    location: "Room 1",
  });

  await openAppointments(page, request, "/appointments?date=2026-01-15");
  await page.getByTestId("appointments-view-calendar").click();

  const event = page.getByTestId(`appointment-event-${appointment.id}`);
  await expect(event).toBeVisible({ timeout: 15_000 });
  await event.click();

  const updatedMeta = page.getByTestId("appointment-updated-meta");
  await expect(updatedMeta).toBeVisible({ timeout: 15_000 });
  const beforeIso = await updatedMeta.getAttribute("data-iso");

  await page.getByRole("button", { name: "Edit" }).click();
  const typeInput = page.getByTestId("edit-appointment-type");
  await typeInput.fill("Checkup");
  await page.getByRole("button", { name: "Save changes" }).click();

  await expect
    .poll(async () => updatedMeta.getAttribute("data-iso"), {
      timeout: 15_000,
    })
    .not.toBe(beforeIso);
});
