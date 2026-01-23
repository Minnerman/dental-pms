import { expect, test } from "@playwright/test";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

type AppointmentItem = {
  legacy_appointment_id: number;
  starts_at: string;
  ends_at: string;
  status_normalised: string;
  status_raw: string;
  clinician_code: number;
  clinician_name: string;
  clinician_role: string;
  clinician_is_current: boolean;
  patient_id: number | null;
  patient_display_name: string;
  is_unlinked: boolean;
  title: string;
  notes: string;
};

test("r4 calendar read-only filters and rendering", async ({ page, request }) => {
  await primePageAuth(page, request);

  const baseItem: AppointmentItem = {
    legacy_appointment_id: 101,
    starts_at: "2025-01-02T09:00:00.000Z",
    ends_at: "2025-01-02T09:30:00.000Z",
    status_normalised: "pending",
    status_raw: "Pending",
    clinician_code: 1001,
    clinician_name: "Dr Core",
    clinician_role: "Dentist",
    clinician_is_current: true,
    patient_id: 501,
    patient_display_name: "Jane Doe",
    is_unlinked: false,
    title: "Check-up",
    notes: "Routine",
  };
  const hiddenItem: AppointmentItem = {
    legacy_appointment_id: 102,
    starts_at: "2025-01-02T10:00:00.000Z",
    ends_at: "2025-01-02T10:30:00.000Z",
    status_normalised: "complete",
    status_raw: "Complete",
    clinician_code: 1002,
    clinician_name: "Dr Hidden",
    clinician_role: "Hygienist",
    clinician_is_current: true,
    patient_id: 502,
    patient_display_name: "Hidden Patient",
    is_unlinked: false,
    title: "Review",
    notes: "Completed",
  };
  const unlinkedItem: AppointmentItem = {
    legacy_appointment_id: 103,
    starts_at: "2025-01-02T11:00:00.000Z",
    ends_at: "2025-01-02T11:30:00.000Z",
    status_normalised: "pending",
    status_raw: "Pending",
    clinician_code: 1003,
    clinician_name: "Dr Unlinked",
    clinician_role: "Dentist",
    clinician_is_current: true,
    patient_id: null,
    patient_display_name: "Unlinked",
    is_unlinked: true,
    title: "Walk-in",
    notes: "Needs mapping",
  };

  await page.route("**/api/api/appointments**", async (route) => {
    const url = new URL(route.request().url());
    const showHiddenParam = url.searchParams.get("show_hidden");
    const showUnlinkedParam = url.searchParams.get("show_unlinked");
    const showHidden = showHiddenParam === "true" || showHiddenParam === "1";
    const showUnlinked = showUnlinkedParam === "true" || showUnlinkedParam === "1";
    const items = [baseItem];
    if (showHidden) items.push(hiddenItem);
    if (showUnlinked) items.push(unlinkedItem);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items, total_count: items.length }),
    });
  });

  const baseUrl = getBaseUrl();
  await page.goto(`${baseUrl}/r4-calendar?from=2025-01-01&to=2025-01-07`, {
    waitUntil: "domcontentloaded",
  });

  await expect(page.getByTestId("r4-calendar-banner")).toBeVisible();
  await expect(page.getByTestId("r4-filter-show-hidden")).not.toBeChecked();
  await expect(page.getByTestId("r4-filter-show-unlinked")).not.toBeChecked();
  await expect(page.getByText("Hidden Patient")).toHaveCount(0);
  await expect(page.getByTestId("r4-unlinked-badge")).toHaveCount(0);

  const showHiddenToggle = page.getByRole("button", { name: /show hidden/i });
  await showHiddenToggle.click();
  await expect(page).toHaveURL(/(\?|&)show_hidden=1(&|$)/, { timeout: 5000 });
  await expect(page.getByTestId("r4-filter-show-hidden")).toBeChecked();
  await expect(page.getByText("Hidden Patient")).toBeVisible();

  const showUnlinkedToggle = page.getByRole("button", { name: /show unlinked/i });
  await showUnlinkedToggle.click();
  await expect(page).toHaveURL(/(\?|&)show_unlinked=1(&|$)/, { timeout: 5000 });
  await expect(page.getByTestId("r4-filter-show-unlinked")).toBeChecked();
  await expect(page.getByTestId("r4-unlinked-badge")).toBeVisible();
});

test("r4 calendar links unlinked appointment to patient", async ({ page, request }) => {
  await primePageAuth(page, request);

  let linked = false;
  const unlinkedItem: AppointmentItem = {
    legacy_appointment_id: 103,
    starts_at: "2025-01-02T11:00:00.000Z",
    ends_at: "2025-01-02T11:30:00.000Z",
    status_normalised: "pending",
    status_raw: "Pending",
    clinician_code: 1003,
    clinician_name: "Dr Unlinked",
    clinician_role: "Dentist",
    clinician_is_current: true,
    patient_id: null,
    patient_display_name: "Unlinked",
    is_unlinked: true,
    title: "Walk-in",
    notes: "Needs mapping",
  };
  const linkedItem: AppointmentItem = {
    ...unlinkedItem,
    patient_id: 901,
    patient_display_name: "Linked Patient",
    is_unlinked: false,
  };

  await page.route("**/api/api/appointments**", async (route) => {
    const items = linked ? [linkedItem] : [unlinkedItem];
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items, total_count: items.length }),
    });
  });

  await page.route("**/api/patients/search**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: 901,
          first_name: "Linked",
          last_name: "Patient",
          date_of_birth: "1990-01-01",
        },
      ]),
    });
  });

  await page.route("**/api/appointments/103/link", async (route) => {
    linked = true;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: 1,
        legacy_source: "r4",
        legacy_appointment_id: 103,
        patient_id: 901,
        linked_by_user_id: 1,
        linked_at: "2025-01-02T12:00:00.000Z",
      }),
    });
  });

  const baseUrl = getBaseUrl();
  await page.goto(`${baseUrl}/r4-calendar?from=2025-01-01&to=2025-01-07&show_unlinked=1`, {
    waitUntil: "domcontentloaded",
  });

  await expect(page.getByTestId("r4-unlinked-badge")).toBeVisible();
  await page.getByTestId("r4-link-appointment-103").click();
  await expect(page.getByTestId("r4-link-modal")).toBeVisible();
  await page.getByTestId("r4-link-search").fill("Linked");
  await page.getByTestId("r4-link-patient-901").click();
  await page.getByTestId("r4-link-save").click();
  await expect(page.getByText("Linked Patient")).toBeVisible();
  await expect(page.getByTestId("r4-unlinked-badge")).toHaveCount(0);
});
