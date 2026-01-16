import { expect, test } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { primePageAuth } from "./helpers/auth";

async function openAppointments(page: any, request: any, url: string) {
  await primePageAuth(page, request);
  await page.goto(url, { waitUntil: "domcontentloaded" });
  await expect(page).toHaveURL(/\/appointments/);
  await expect(page).not.toHaveURL(/\/change-password|\/login/);
  await expect(page.getByTestId("appointments-page")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("new-appointment")).toBeVisible({ timeout: 15_000 });
}

async function clickNewAppointment(page: any) {
  const button = page.getByTestId("new-appointment");
  await expect(button).toBeVisible({ timeout: 15_000 });
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      await button.click();
      return;
    } catch (error) {
      if (attempt === 2) throw error;
      await page.waitForTimeout(250);
    }
  }
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
  await expect(page.getByTestId("booking-location-room")).toBeVisible({ timeout: 15_000 });
  await page.getByTestId("booking-location-room").fill("Room 1");
  await expect(page.getByTestId("booking-visit-address")).toBeVisible({ timeout: 15_000 });
  await page.getByTestId("booking-visit-address").fill("123 Test Street");
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 10_000 });
});

test("appointment creation uses latest clinician and location selections", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const lastName = `Patient ${unique}`;
  const patientId = await createPatient(request, {
    first_name: "Test",
    last_name: lastName,
  });
  await openAppointments(page, request, "/appointments?date=2026-01-15");
  await clickNewAppointment(page);
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 10_000 });

  const patientSearch = page.getByTestId("booking-patient-search");
  await patientSearch.fill(lastName);
  const patientSelect = page.getByTestId("booking-patient-select");
  await expect(patientSelect.locator(`option[value="${patientId}"]`)).toHaveCount(
    1,
    { timeout: 15_000 }
  );
  await patientSelect.selectOption(String(patientId));
  await expect(patientSelect).toHaveValue(String(patientId));

  await page.getByLabel("Start").fill("2026-01-15T09:00");
  await page.getByLabel("End").fill("2026-01-15T09:30");

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

  await page.getByRole("button", { name: "Create appointment" }).click();
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
