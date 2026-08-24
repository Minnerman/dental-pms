import { expect, test, type Page } from "@playwright/test";

import { createAppointment, createAppointmentNote, createPatient } from "./helpers/api";
import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

async function mockCapabilities(page: Page, capabilities: string[]) {
  await page.route("**/api/me/capabilities", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(capabilities),
    });
  });
}

async function createPatientNote(
  request: Parameters<typeof ensureAuthReady>[0],
  patientId: string,
  body: string
) {
  const token = await ensureAuthReady(request);
  const response = await request.post(
    `${getBaseUrl()}/api/patients/${patientId}/notes`,
    {
      headers: { Authorization: `Bearer ${token}` },
      data: { body, note_type: "clinical" },
    }
  );
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as { id: number };
}

test("global Notes worklist is safely read-only with notes.view only", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Notes",
    last_name: `Viewer ${Date.now()}`,
  });
  const noteBody = `Synthetic view-only note ${Date.now()}`;
  const note = await createPatientNote(request, patientId, noteBody);
  await primePageAuth(page, request);
  await mockCapabilities(page, ["notes.view"]);

  const writeRequests: string[] = [];
  page.on("request", (browserRequest) => {
    if (["POST", "PUT", "PATCH", "DELETE"].includes(browserRequest.method())) {
      writeRequests.push(browserRequest.method());
    }
  });

  await page.goto(`${getBaseUrl()}/notes?note=${note.id}`, {
    waitUntil: "domcontentloaded",
  });

  await expect(page.getByTestId("notes-capability-state")).toHaveAttribute(
    "data-state",
    "read-only"
  );
  await expect(page.getByTestId("note-detail-readonly")).toContainText(noteBody);
  await expect(page.getByTestId("note-detail-audit")).toBeVisible();
  await expect(page.getByTestId("note-detail-body")).toHaveCount(0);
  await expect(page.getByTestId("note-detail-save")).toHaveCount(0);
  await expect(page.getByTestId("note-detail-archive")).toHaveCount(0);
  expect(writeRequests).toEqual([]);
});

test("global Notes blocks content when capability verification fails", async ({
  page,
  request,
}) => {
  await primePageAuth(page, request);
  let listRequests = 0;
  await page.route("**/api/me/capabilities", async (route) => {
    await route.fulfill({
      status: 500,
      contentType: "text/html",
      body: "<h1>private upstream failure</h1>",
    });
  });
  await page.route("**/api/notes?*", async (route) => {
    listRequests += 1;
    await route.continue();
  });

  await page.goto(`${getBaseUrl()}/notes`, { waitUntil: "domcontentloaded" });

  await expect(page.getByTestId("notes-capability-state")).toHaveAttribute(
    "data-state",
    "denied"
  );
  await expect(page.getByText("Note permissions could not be verified.")).toBeVisible();
  await expect(page.getByTestId("notes-worklist")).toHaveCount(0);
  await expect(page.getByText("private upstream failure")).toHaveCount(0);
  expect(listRequests).toBe(0);
});

test("global Notes uses a fixed safe API error and no raw patient id fallback", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Notes",
    last_name: `Unavailable ${Date.now()}`,
  });
  await createPatientNote(request, patientId, `Synthetic safe-error note ${Date.now()}`);
  await primePageAuth(page, request);
  await mockCapabilities(page, ["notes.view", "notes.write"]);
  await page.route("**/api/patients?*", async (route) => {
    await route.fulfill({ status: 500, contentType: "text/html", body: "private html" });
  });

  await page.goto(`${getBaseUrl()}/notes`, { waitUntil: "domcontentloaded" });

  await expect(page.getByText("Patient unavailable").first()).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText(new RegExp(`Patient #${patientId}`))).toHaveCount(0);
  await expect(page.getByText("private html")).toHaveCount(0);

  await page.route("**/api/notes?*", async (route) => {
    await route.fulfill({
      status: 500,
      contentType: "text/html",
      body: "<h1>private response body</h1>",
    });
  });
  await page.getByRole("button", { name: "Refresh" }).click();
  await expect(page.getByText("Failed to load notes.")).toBeVisible();
  await expect(page.getByText("private response body")).toHaveCount(0);
});

test("patient and appointment note controls are read-only without notes.write", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const patientId = await createPatient(request, {
    first_name: "Notes",
    last_name: `Read only ${unique}`,
  });
  const patientNoteBody = `Synthetic patient read-only note ${Date.now()}`;
  await createPatientNote(request, patientId, patientNoteBody);
  const appointment = await createAppointment(request, patientId, {
    starts_at: "2030-01-16T10:00:00.000Z",
    ends_at: "2030-01-16T10:30:00.000Z",
  });
  const appointmentNoteBody = `Synthetic appointment read-only note ${Date.now()}`;
  const appointmentNote = await createAppointmentNote(request, appointment.id, {
    body: appointmentNoteBody,
  });

  await primePageAuth(page, request);
  await mockCapabilities(page, [
    "patients.view",
    "clinical.view",
    "appointments.view",
    "notes.view",
  ]);
  await page.goto(`${getBaseUrl()}/patients/${patientId}/clinical`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("patient-tabs")).toBeVisible({ timeout: 20_000 });
  await page.getByTestId("patient-tab-Notes").click();
  await expect(page.getByTestId("patient-notes-access")).toHaveAttribute(
    "data-state",
    "read-only"
  );
  await expect(page.getByText(patientNoteBody, { exact: true })).toBeVisible();
  await expect(page.getByTestId("patient-note-add")).toHaveCount(0);

  await page.goto(`${getBaseUrl()}/appointments?date=2030-01-16&view=day`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("appointments-page")).toBeVisible({ timeout: 20_000 });
  await page.getByTestId("appointments-view-day-sheet").click();
  const appointmentRow = page
    .locator(".day-sheet-table tbody tr")
    .filter({ hasText: `Read only ${unique}` })
    .first();
  await expect(appointmentRow).toBeVisible({ timeout: 20_000 });
  await appointmentRow.click();
  await page.keyboard.press("Enter");
  const detailPanel = page.getByTestId("appointment-detail-panel");
  await expect(detailPanel).toBeVisible({ timeout: 15_000 });
  await expect(detailPanel.getByTestId("appointment-notes-access")).toContainText(
    "read-only"
  );
  await expect(detailPanel.getByText(appointmentNoteBody, { exact: true })).toBeVisible();
  await expect(detailPanel.getByTestId("appointment-detail-add-note")).toHaveCount(0);
  await expect(
    detailPanel.getByTestId(`appointment-note-edit-${appointmentNote.id}`)
  ).toHaveCount(0);
  await expect(
    detailPanel.getByTestId(`appointment-note-archive-${appointmentNote.id}`)
  ).toHaveCount(0);
  await expect(detailPanel.getByRole("link", { name: "Audit" })).toBeVisible();
});
