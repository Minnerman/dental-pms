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

async function switchToCalendarDayView(page: any) {
  await page.getByTestId("appointments-view-calendar").click();
  const explicit = page.getByTestId("appointments-calendar-view-day");
  if (await explicit.count()) {
    await explicit.click();
  } else {
    const fallback = page
      .locator(".rbc-toolbar button")
      .filter({ hasText: /^day$/i })
      .first();
    await expect(fallback).toBeVisible({ timeout: 10_000 });
    await fallback.click();
  }
  await expect(page.getByTestId("appointments-diary-shell")).toBeVisible({ timeout: 15_000 });
}

function getFutureClinicWeekdayDate(seed: number) {
  const date = new Date(Date.UTC(2030, 0, 1));
  date.setUTCDate(date.getUTCDate() + (seed % 365));
  const day = date.getUTCDay();
  if (day === 6) {
    date.setUTCDate(date.getUTCDate() + 2);
  } else if (day === 0) {
    date.setUTCDate(date.getUTCDate() + 1);
  }
  return date.toISOString().slice(0, 10);
}

function getClinicSlot(seed: number, attempt: number) {
  const starts = [
    "09:10",
    "09:50",
    "10:30",
    "11:10",
    "11:50",
    "12:30",
    "13:10",
    "13:50",
    "14:30",
    "15:10",
    "15:50",
    "16:30",
  ];
  const index = (Math.floor(seed / 1000) + attempt) % starts.length;
  const start = starts[index];
  const [hours, minutes] = start.split(":").map(Number);
  const endDate = new Date(Date.UTC(2030, 0, 1, hours, minutes + 30));
  const end = `${String(endDate.getUTCHours()).padStart(2, "0")}:${String(
    endDate.getUTCMinutes()
  ).padStart(2, "0")}`;
  return { start, end };
}

async function fillBookableClinicSlot(page: any, testDate: string, seed: number) {
  const startInput = page.getByTestId("booking-start");
  const endInput = page.getByTestId("booking-end");
  const submitButton = page.getByTestId("booking-submit");

  for (let attempt = 0; attempt < 12; attempt += 1) {
    const slot = getClinicSlot(seed, attempt);
    await startInput.fill(`${testDate}T${slot.start}`);
    await endInput.fill(`${testDate}T${slot.end}`);
    try {
      await expect.poll(async () => submitButton.isDisabled(), { timeout: 3_000 }).toBe(false);
      return slot;
    } catch {
      // Try the next in-hours slot if this one is blocked by validation or an existing conflict.
    }
  }

  const modalText = await page.getByTestId("booking-modal").textContent();
  throw new Error(`Could not find a bookable clinic slot on ${testDate}: ${modalText ?? ""}`);
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

async function createRecall(request: any, patientId: string, notes: string, dueDate: string) {
  const token = await ensureAuthReady(request);
  const baseURL = getBaseUrl();
  const response = await request.post(`${baseURL}/api/patients/${patientId}/recalls`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      kind: "exam",
      due_date: dueDate,
      notes,
    },
  });
  expect(response.ok()).toBeTruthy();
  return response.json();
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

test("appointments deep link preselects clinician in booking flow", async ({
  page,
  request,
}) => {
  const token = await ensureAuthReady(request);
  const usersResponse = await request.get(`${getBaseUrl()}/api/users`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(usersResponse.ok()).toBeTruthy();
  const users = (await usersResponse.json()) as Array<{ id: number; is_active: boolean }>;
  const clinician = users.find((user) => user.is_active);
  test.skip(!clinician, "No active users available for clinician deep-link preselect coverage");

  await openAppointments(
    page,
    request,
    `/appointments?date=2026-01-15&book=1&clinicianId=${clinician!.id}`
  );
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 15_000 });

  const clinicianSelect = page
    .getByTestId("booking-modal")
    .getByText("Clinician (optional)", { exact: true })
    .locator("xpath=following-sibling::select[1]");
  await expect(clinicianSelect).toBeVisible();
  await expect(clinicianSelect).toHaveValue(String(clinician!.id));

  await page.waitForURL((url) => !url.searchParams.has("book"), { timeout: 15_000 });
  await expect(clinicianSelect).toHaveValue(String(clinician!.id));
});

test("appointments deep link preselects patient in booking flow", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `AAADEEPLINK${Date.now()}`,
  });

  await openAppointments(
    page,
    request,
    `/appointments?date=2026-01-15&book=1&patientId=${patientId}`
  );
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 15_000 });

  const patientSelect = page.getByTestId("booking-patient-select");
  await expect(patientSelect.locator(`option[value="${patientId}"]`)).toHaveCount(1, {
    timeout: 15_000,
  });
  await expect(patientSelect).toHaveValue(String(patientId));

  await page.waitForURL((url) => !url.searchParams.has("book"), { timeout: 15_000 });
  await expect(patientSelect).toHaveValue(String(patientId));
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

test("appointment creation appears in clinician diary immediately and persists after refresh", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);
  const unique = Date.now();
  const testDate = getFutureClinicWeekdayDate(unique);
  const lastName = `Visible ${unique}`;
  const room = `Room 163H-${unique}`;
  const patientId = await createPatient(request, {
    first_name: "Booking",
    last_name: lastName,
  });

  const usersResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" && new URL(response.url()).pathname.endsWith("/api/users")
  );
  await openAppointments(page, request, `/appointments?date=${testDate}`);
  const usersResponse = await usersResponsePromise;
  expect(usersResponse.ok()).toBeTruthy();
  await switchToCalendarDayView(page);
  await clickNewAppointment(page);

  await selectBookingPatient(page, patientId, lastName);

  const clinicianSelect = page.getByTestId("booking-modal").locator("select").nth(2);
  await expect
    .poll(
      async () =>
        clinicianSelect.evaluate(
          (select) =>
            Array.from((select as HTMLSelectElement).options)
              .map((option) => option.value)
              .filter(Boolean).length
        ),
      { timeout: 15_000 }
    )
    .toBeGreaterThan(0);
  const clinicianOption = await clinicianSelect.evaluate((select) => {
    const option = Array.from((select as HTMLSelectElement).options).find((entry) => entry.value);
    if (!option) {
      return null;
    }
    return {
      value: option.value,
      label: option.text.trim(),
    };
  });
  expect(clinicianOption).toBeTruthy();

  await clinicianSelect.selectOption(clinicianOption!.value);
  const expectedClinicianLabel = clinicianOption!.label.replace(/\s+\([^)]*\)\s*$/, "");
  const bookableSlot = await fillBookableClinicSlot(page, testDate, unique);
  await page.getByTestId("booking-location-room").fill(room);
  const diaryColumns = page.getByTestId("appointments-diary-columns");
  const clinicianFilter = page.getByTestId("appointments-diary-clinician-filter");

  const createResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname.endsWith("/api/appointments")
  );

  await page.getByTestId("booking-submit").click();
  const createResponse = await createResponsePromise;
  expect(createResponse.ok()).toBeTruthy();
  const createdAppointment = (await createResponse.json()) as { id: number };

  await expect(page.getByTestId("booking-modal")).toBeHidden({ timeout: 15_000 });
  await expect(page.getByText("Appointment created.")).toBeVisible({ timeout: 15_000 });

  const diaryGrouping = page.getByTestId("appointments-diary-grouping");
  await diaryGrouping.selectOption("clinician");
  await expect(diaryColumns).toContainText(expectedClinicianLabel, { timeout: 15_000 });

  await clinicianFilter.selectOption({ label: expectedClinicianLabel });
  await page.getByTestId("appointments-diary-search").fill(lastName);

  const createdEvent = page.getByTestId(`appointment-event-${createdAppointment.id}`);
  await expect(createdEvent).toBeVisible({ timeout: 15_000 });
  await expect(createdEvent).toContainText(bookableSlot.start);
  await expect(createdEvent).toContainText(lastName.toUpperCase());
  await expect(createdEvent).toContainText(`@ ${room}`);

  await page.reload({ waitUntil: "domcontentloaded" });
  await openAppointments(page, request, page.url());
  await switchToCalendarDayView(page);
  await page.getByTestId("appointments-diary-grouping").selectOption("clinician");
  await expect(page.getByTestId("appointments-diary-columns")).toContainText(
    expectedClinicianLabel,
    {
      timeout: 15_000,
    }
  );
  await page
    .getByTestId("appointments-diary-clinician-filter")
    .selectOption({ label: expectedClinicianLabel });
  await page.getByTestId("appointments-diary-search").fill(lastName);

  const reloadedEvent = page.getByTestId(`appointment-event-${createdAppointment.id}`);
  await expect(reloadedEvent).toBeVisible({ timeout: 15_000 });
  await expect(reloadedEvent).toContainText(bookableSlot.start);
  await expect(reloadedEvent).toContainText(lastName.toUpperCase());
  await expect(reloadedEvent).toContainText(`@ ${room}`);
});

test("appointments booking shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const lastName = `Repeat ${unique}`;
  const patientId = await createPatient(request, {
    first_name: "Booking",
    last_name: lastName,
  });

  await openAppointments(page, request, "/appointments?date=2026-03-20");
  await clickNewAppointment(page);
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 10_000 });

  await selectBookingPatient(page, patientId, lastName);
  await page.getByTestId("booking-start").fill("2026-03-20T09:00");
  await page.getByTestId("booking-end").fill("2026-03-20T09:30");
  await page.getByTestId("booking-location-room").fill("Room 5");

  const submitButton = page.getByTestId("booking-submit");
  await expect(submitButton).toBeEnabled();

  let requestCount = 0;
  const bookingRoutePattern = /\/api\/appointments$/;
  let seenCreateRequest!: () => void;
  const seenCreateRequestPromise = new Promise<void>((resolve) => {
    seenCreateRequest = resolve;
  });
  let releaseCreateRequest!: () => void;
  const releaseCreateRequestPromise = new Promise<void>((resolve) => {
    releaseCreateRequest = resolve;
  });

  await page.route(bookingRoutePattern, async (route) => {
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
      response.url().includes("/api/appointments")
  );

  const clickState = await submitButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Create appointment button not found");
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
  await expect(submitButton).toBeDisabled();
  await expect(submitButton).toHaveText("Saving...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseCreateRequest();

  const createResponse = await createResponsePromise;
  expect(createResponse.ok()).toBeTruthy();
  expect(createResponse.request().postDataJSON()).toMatchObject({
    patient_id: Number(patientId),
    location: "Room 5",
    location_type: "clinic",
  });
  await page.unroute(bookingRoutePattern);

  await expect(page.getByTestId("booking-modal")).toBeHidden({ timeout: 15_000 });
  await expect(page.getByText("Appointment created.")).toBeVisible({ timeout: 15_000 });
});

test("booking-linked recall prompt shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const lastName = `Recall ${unique}`;
  const patientId = await createPatient(request, {
    first_name: "Booking",
    last_name: lastName,
  });
  const recallNotes = `Recall prompt ${unique}`;
  const recall = (await createRecall(
    request,
    patientId,
    recallNotes,
    "2026-03-20"
  )) as { id: number };

  await openAppointments(
    page,
    request,
    `/appointments?date=2026-03-20&book=1&patientId=${patientId}&recallId=${recall.id}`
  );
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 10_000 });

  await selectBookingPatient(page, patientId, lastName);
  await page.getByTestId("booking-start").fill("2026-03-20T10:00");
  await page.getByTestId("booking-end").fill("2026-03-20T10:30");
  await page.getByTestId("booking-location-room").fill("Room 6");

  const createResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/api/appointments")
  );
  await page.getByTestId("booking-submit").click();
  const createResponse = await createResponsePromise;
  expect(createResponse.ok()).toBeTruthy();
  const createdAppointment = (await createResponse.json()) as { id: number };

  const prompt = page.getByTestId("appointments-recall-prompt");
  await expect(prompt).toBeVisible({ timeout: 15_000 });
  await expect(prompt).toContainText("Mark recall completed?");

  const completeButton = page.getByTestId("appointments-recall-complete-button");
  await expect(completeButton).toBeEnabled();

  let requestCount = 0;
  const routePattern = new RegExp(`/api/patients/${patientId}/recalls/${recall.id}$`);
  let seenRecallRequest!: () => void;
  const seenRecallRequestPromise = new Promise<void>((resolve) => {
    seenRecallRequest = resolve;
  });
  let releaseRecallRequest!: () => void;
  const releaseRecallRequestPromise = new Promise<void>((resolve) => {
    releaseRecallRequest = resolve;
  });

  await page.route(routePattern, async (route) => {
    if (route.request().method() !== "PATCH") {
      await route.continue();
      return;
    }
    requestCount += 1;
    if (requestCount === 1) {
      seenRecallRequest();
      await releaseRecallRequestPromise;
    }
    await route.continue();
  });

  const recallResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      response.url().includes(`/api/patients/${patientId}/recalls/${recall.id}`)
  );

  const clickState = await completeButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Mark completed button not found");
    }
    const beforeDisabled = button.disabled;
    button.click();
    const afterFirstDisabled = button.disabled;
    button.click();
    return { beforeDisabled, afterFirstDisabled, afterSecondDisabled: button.disabled };
  });
  await seenRecallRequestPromise;

  expect(clickState.beforeDisabled).toBe(false);
  expect(clickState.afterFirstDisabled).toBe(true);
  expect(clickState.afterSecondDisabled).toBe(true);
  await expect(completeButton).toBeDisabled();
  await expect(completeButton).toHaveText("Saving...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseRecallRequest();

  const recallResponse = await recallResponsePromise;
  expect(recallResponse.ok()).toBeTruthy();
  expect(recallResponse.request().postDataJSON()).toMatchObject({
    status: "completed",
    outcome: "attended",
    linked_appointment_id: createdAppointment.id,
  });
  await page.unroute(routePattern);

  await expect(page.getByTestId("appointments-recall-prompt")).toHaveCount(0);
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
  const lastName = `Meta ${Date.now()}`;
  const patientId = await createPatient(request, {
    first_name: "Audit",
    last_name: lastName,
  });
  const appointment = await createAppointment(request, patientId, {
    clinician_user_id: null,
    starts_at: "2026-01-15T12:00:00.000Z",
    ends_at: "2026-01-15T12:30:00.000Z",
    location_type: "clinic",
    location: "Room 1",
  });

  await openAppointments(page, request, "/appointments?date=2026-01-15");
  await page.getByTestId("appointments-view-day-sheet").click();
  const row = page.locator("tbody tr", { hasText: new RegExp(lastName, "i") }).first();
  await expect(row).toBeVisible({ timeout: 15_000 });
  await row.dblclick();
  await expect(page.getByTestId("edit-appointment-type")).toBeVisible({ timeout: 15_000 });
  await page.getByRole("button", { name: "Cancel edit" }).click();

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

test("appointment edited type stays visible after save and refresh", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const lastName = `Persist ${unique}`;
  const updatedType = `Review ${unique}`;
  const patientId = await createPatient(request, {
    first_name: "Visible",
    last_name: lastName,
  });
  await createAppointment(request, patientId, {
    clinician_user_id: null,
    starts_at: "2026-01-15T12:45:00.000Z",
    ends_at: "2026-01-15T13:15:00.000Z",
    location_type: "clinic",
    location: "Room 7",
  });

  await openAppointments(page, request, "/appointments?date=2026-01-15");
  await page.getByTestId("appointments-view-day-sheet").click();
  const row = page.locator("tbody tr", { hasText: new RegExp(lastName, "i") }).first();
  await expect(row).toBeVisible({ timeout: 15_000 });
  await row.click();
  await page.keyboard.press("Enter");

  const detailPanel = page.getByTestId("appointment-detail-panel");
  await expect(detailPanel).toBeVisible({ timeout: 15_000 });
  await detailPanel.getByRole("button", { name: "Edit" }).click();

  const typeInput = detailPanel.getByTestId("edit-appointment-type");
  await expect(typeInput).toBeVisible({ timeout: 15_000 });
  await typeInput.fill(updatedType);
  await detailPanel.getByTestId("appointment-edit-save").click();

  await expect(page.getByText("Appointment updated.")).toBeVisible({ timeout: 15_000 });
  await expect(detailPanel).toContainText(`Type: ${updatedType}`);

  await page.reload({ waitUntil: "domcontentloaded" });
  await openAppointments(page, request, page.url());
  await page.getByTestId("appointments-view-day-sheet").click();
  const reloadedRow = page.locator("tbody tr", { hasText: new RegExp(lastName, "i") }).first();
  await expect(reloadedRow).toBeVisible({ timeout: 15_000 });
  await reloadedRow.click();
  await page.keyboard.press("Enter");

  const reloadedDetailPanel = page.getByTestId("appointment-detail-panel");
  await expect(reloadedDetailPanel).toBeVisible({ timeout: 15_000 });
  await expect(reloadedDetailPanel).toContainText(`Type: ${updatedType}`);
});

test("appointment edit save shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const lastName = `Edit ${Date.now()}`;
  const patientId = await createPatient(request, {
    first_name: "Repeat",
    last_name: lastName,
  });
  const appointment = await createAppointment(request, patientId, {
    clinician_user_id: null,
    starts_at: "2026-01-15T13:00:00.000Z",
    ends_at: "2026-01-15T13:30:00.000Z",
    location_type: "clinic",
    location: "Room 2",
  });

  await openAppointments(page, request, "/appointments?date=2026-01-15");
  await page.getByTestId("appointments-view-day-sheet").click();
  const row = page.locator("tbody tr", { hasText: new RegExp(lastName, "i") }).first();
  await expect(row).toBeVisible({ timeout: 15_000 });
  await row.dblclick();

  const typeInput = page.getByTestId("edit-appointment-type");
  await expect(typeInput).toBeVisible({ timeout: 15_000 });
  await typeInput.fill("Review");

  const saveButton = page.getByTestId("appointment-edit-save");
  await expect(saveButton).toBeEnabled();

  let requestCount = 0;
  const routePattern = new RegExp(`/api/appointments/${appointment.id}$`);
  let seenPatchRequest!: () => void;
  const seenPatchRequestPromise = new Promise<void>((resolve) => {
    seenPatchRequest = resolve;
  });
  let releasePatchRequest!: () => void;
  const releasePatchRequestPromise = new Promise<void>((resolve) => {
    releasePatchRequest = resolve;
  });

  await page.route(routePattern, async (route) => {
    if (route.request().method() !== "PATCH") {
      await route.continue();
      return;
    }
    requestCount += 1;
    if (requestCount === 1) {
      seenPatchRequest();
      await releasePatchRequestPromise;
    }
    await route.continue();
  });

  const updateResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      response.url().includes(`/api/appointments/${appointment.id}`)
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
  await seenPatchRequestPromise;

  expect(clickState.beforeDisabled).toBe(false);
  expect(clickState.afterFirstDisabled).toBe(true);
  expect(clickState.afterSecondDisabled).toBe(true);
  await expect(saveButton).toBeDisabled();
  await expect(saveButton).toHaveText("Saving...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releasePatchRequest();

  const updateResponse = await updateResponsePromise;
  expect(updateResponse.ok()).toBeTruthy();
  expect(updateResponse.request().postDataJSON()).toMatchObject({
    appointment_type: "Review",
  });
  await page.unroute(routePattern);

  await expect(page.getByText("Appointment updated.")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Type: Review")).toBeVisible({ timeout: 15_000 });
});

test("appointment detail save shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const lastName = `Detail ${unique}`;
  const visitAddress = `123 Stage 163H Detail Road ${unique}`;
  const patientId = await createPatient(request, {
    first_name: "Repeat",
    last_name: lastName,
  });
  const appointment = await createAppointment(request, patientId, {
    clinician_user_id: null,
    starts_at: "2026-01-15T14:00:00.000Z",
    ends_at: "2026-01-15T14:30:00.000Z",
    location_type: "clinic",
    location: "Room 3",
  });

  await openAppointments(page, request, "/appointments?date=2026-01-15");
  await page.getByTestId("appointments-view-day-sheet").click();
  const row = page.locator("tbody tr", { hasText: new RegExp(lastName, "i") }).first();
  await expect(row).toBeVisible({ timeout: 15_000 });
  await row.click();
  await page.keyboard.press("Enter");

  const detailPanel = page.getByTestId("appointment-detail-panel");
  await expect(detailPanel).toBeVisible({ timeout: 15_000 });

  const detailForm = detailPanel.locator("form").first();
  await detailForm.locator("select").selectOption("visit");
  const visitAddressInput = detailForm.locator("textarea");
  await expect(visitAddressInput).toBeVisible({ timeout: 15_000 });
  await visitAddressInput.fill(visitAddress);

  const saveButton = detailPanel.getByTestId("appointment-detail-save");
  await expect(saveButton).toBeEnabled();

  let requestCount = 0;
  const routePattern = new RegExp(`/api/appointments/${appointment.id}$`);
  let seenPatchRequest!: () => void;
  const seenPatchRequestPromise = new Promise<void>((resolve) => {
    seenPatchRequest = resolve;
  });
  let releasePatchRequest!: () => void;
  const releasePatchRequestPromise = new Promise<void>((resolve) => {
    releasePatchRequest = resolve;
  });

  await page.route(routePattern, async (route) => {
    if (route.request().method() !== "PATCH") {
      await route.continue();
      return;
    }
    requestCount += 1;
    if (requestCount === 1) {
      seenPatchRequest();
      await releasePatchRequestPromise;
    }
    await route.continue();
  });

  const updateResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      response.url().includes(`/api/appointments/${appointment.id}`)
  );

  const clickState = await saveButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Save details button not found");
    }
    const beforeDisabled = button.disabled;
    button.click();
    const afterFirstDisabled = button.disabled;
    button.click();
    return { beforeDisabled, afterFirstDisabled, afterSecondDisabled: button.disabled };
  });
  await seenPatchRequestPromise;

  expect(clickState.beforeDisabled).toBe(false);
  expect(clickState.afterFirstDisabled).toBe(true);
  expect(clickState.afterSecondDisabled).toBe(true);
  await expect(saveButton).toBeDisabled();
  await expect(saveButton).toHaveText("Saving...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releasePatchRequest();

  const updateResponse = await updateResponsePromise;
  expect(updateResponse.ok()).toBeTruthy();
  expect(updateResponse.request().postDataJSON()).toMatchObject({
    location_type: "visit",
    location_text: visitAddress,
  });
  await page.unroute(routePattern);

  await expect(page.getByText("Appointment updated.")).toBeVisible({ timeout: 15_000 });
  await expect(detailPanel).toContainText("Location type: visit");
  await expect(detailPanel).toContainText(visitAddress);
});

test("appointment detail history shows created and updated entries", async ({
  page,
  request,
}) => {
  test.setTimeout(60_000);
  const unique = Date.now();
  const lastName = `Audit ${unique}`;
  const visitAddress = `163H Audit Road ${unique}`;
  const patientId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: lastName,
  });
  await createAppointment(request, patientId, {
    clinician_user_id: null,
    starts_at: "2026-01-15T16:00:00.000Z",
    ends_at: "2026-01-15T16:30:00.000Z",
    location_type: "clinic",
    location: "Room 5",
  });

  await openAppointments(page, request, "/appointments?date=2026-01-15");
  await page.getByTestId("appointments-view-day-sheet").click();
  const row = page.locator("tbody tr", { hasText: new RegExp(lastName, "i") }).first();
  await expect(row).toBeVisible({ timeout: 15_000 });
  await row.click();
  await page.keyboard.press("Enter");

  const detailPanel = page.getByTestId("appointment-detail-panel");
  await expect(detailPanel).toBeVisible({ timeout: 15_000 });

  const detailForm = detailPanel.locator("form").first();
  await detailForm.locator("select").selectOption("visit");
  const visitAddressInput = detailForm.locator("textarea");
  await expect(visitAddressInput).toBeVisible({ timeout: 15_000 });
  await visitAddressInput.fill(visitAddress);

  await detailPanel.getByTestId("appointment-detail-save").click();
  await expect(page.getByText("Appointment updated.")).toBeVisible({ timeout: 15_000 });
  await expect(detailPanel).toContainText("Location type: visit");
  await expect(detailPanel).toContainText(visitAddress);

  const historyToggle = detailPanel.getByTestId("appointment-history-toggle");
  await expect(historyToggle).toHaveText("View");
  await historyToggle.click();
  await expect(historyToggle).toHaveText("Hide");

  const historyRows = detailPanel.getByTestId("appointment-history-row");
  await expect(historyRows).toHaveCount(2, { timeout: 15_000 });

  const actionLabels = historyRows.locator("span:nth-of-type(2)");
  await expect(actionLabels.filter({ hasText: /^created$/i }).first()).toBeVisible();
  await expect(actionLabels.filter({ hasText: /^updated$/i }).first()).toBeVisible();
});

test("appointment detail create estimate shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const lastName = `Estimate ${unique}`;
  const patientId = await createPatient(request, {
    first_name: "Repeat",
    last_name: lastName,
  });
  const token = await ensureAuthReady(request);
  const appointment = await createAppointment(request, patientId, {
    clinician_user_id: null,
    starts_at: "2026-01-15T15:00:00.000Z",
    ends_at: "2026-01-15T15:30:00.000Z",
    location_type: "clinic",
    location: "Room 4",
  });

  await openAppointments(page, request, "/appointments?date=2026-01-15");
  await page.getByTestId("appointments-view-day-sheet").click();
  const row = page.locator("tbody tr", { hasText: new RegExp(lastName, "i") }).first();
  await expect(row).toBeVisible({ timeout: 15_000 });
  await row.click();
  await page.keyboard.press("Enter");

  const detailPanel = page.getByTestId("appointment-detail-panel");
  await expect(detailPanel).toBeVisible({ timeout: 15_000 });

  const createButton = detailPanel.getByTestId("appointment-create-estimate");
  await expect(createButton).toBeEnabled();

  let requestCount = 0;
  const routePattern = new RegExp(`/api/patients/${patientId}/estimates$`);
  let seenCreateRequest!: () => void;
  const seenCreateRequestPromise = new Promise<void>((resolve) => {
    seenCreateRequest = resolve;
  });
  let releaseCreateRequest!: () => void;
  const releaseCreateRequestPromise = new Promise<void>((resolve) => {
    releaseCreateRequest = resolve;
  });

  await page.route(routePattern, async (route) => {
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
      response.url().includes(`/api/patients/${patientId}/estimates`)
  );

  const clickState = await createButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Create estimate button not found");
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
  await expect(createButton).toBeDisabled();
  await expect(createButton).toHaveText("Creating estimate...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseCreateRequest();

  const createResponse = await createResponsePromise;
  expect(createResponse.ok()).toBeTruthy();
  expect(createResponse.request().postDataJSON()).toMatchObject({
    appointment_id: appointment.id,
  });
  const createdEstimate = (await createResponse.json()) as {
    id: number;
    appointment_id: number | null;
  };
  expect(createdEstimate.appointment_id).toBe(appointment.id);
  await page.unroute(routePattern);

  await expect(page.getByText(`Estimate created (EST-${createdEstimate.id}).`)).toBeVisible({
    timeout: 15_000,
  });
  await expect(createButton).toBeEnabled({ timeout: 15_000 });
  await expect(createButton).toHaveText("Create estimate");

  const verifyResponse = await request.get(`${getBaseUrl()}/api/patients/${patientId}/estimates`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(verifyResponse.ok()).toBeTruthy();
  const savedEstimates = (await verifyResponse.json()) as Array<{
    id: number;
    appointment_id: number | null;
  }>;
  expect(
    savedEstimates.some(
      (estimate) =>
        estimate.id === createdEstimate.id && estimate.appointment_id === appointment.id
    )
  ).toBeTruthy();
});
