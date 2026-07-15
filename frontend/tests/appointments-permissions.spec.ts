import { expect, test } from "@playwright/test";

import { createAppointment, createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

async function mockCapabilities(page: any, capabilities: string[]) {
  await page.route("**/api/me/capabilities", async (route: any) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(capabilities),
    });
  });
}

test("appointment controls reflect view-only permissions", async ({ page, request }) => {
  const patientId = await createPatient(request, {
    first_name: "Permission",
    last_name: `Viewer ${Date.now()}`,
  });
  const appointment = await createAppointment(request, patientId, {
    starts_at: "2030-01-15T10:00:00.000Z",
    ends_at: "2030-01-15T10:30:00.000Z",
    location_type: "clinic",
    location: "Permission Room",
  });

  await primePageAuth(page, request);
  await mockCapabilities(page, ["appointments.view"]);
  await page.goto(`${getBaseUrl()}/appointments?date=2030-01-15&view=day&book=1`, {
    waitUntil: "domcontentloaded",
  });

  await expect(page.getByTestId("appointments-page")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("new-appointment")).toHaveCount(0);
  await expect(page.getByTestId("booking-modal")).toHaveCount(0);
  await expect(
    page.getByText("You can view appointments, but you cannot create them.")
  ).toBeVisible();

  await page.getByTestId("appointments-view-calendar").click();
  const eventCard = page.getByTestId(`appointment-event-${appointment.id}`);
  await expect(eventCard).toBeVisible({ timeout: 20_000 });
  await eventCard.click({ button: "right" });

  const contextMenu = page.getByTestId("appointments-context-menu");
  await expect(contextMenu).toBeVisible();
  await expect(contextMenu.getByTestId("appointments-context-open")).toBeVisible();
  await expect(contextMenu.getByTestId("appointments-context-arrived")).toHaveCount(0);
  await expect(contextMenu.getByTestId("appointments-context-cancel")).toHaveCount(0);
  await expect(contextMenu.getByTestId("appointments-context-move")).toHaveCount(0);
  await expect(contextMenu.getByTestId("appointments-context-copy")).toHaveCount(0);

  await contextMenu.getByTestId("appointments-context-open").click();
  await expect(page.getByTestId("appointment-detail-panel")).toBeVisible();
  await expect(page.getByTestId("appointment-detail-edit")).toHaveCount(0);
  await expect(page.getByTestId("appointment-detail-save")).toHaveCount(0);
});

test("patient-led booking hides creation controls without appointment write", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Permission",
    last_name: `Patient booking ${Date.now()}`,
  });

  await primePageAuth(page, request);
  await mockCapabilities(page, ["appointments.view"]);
  await page.goto(`${getBaseUrl()}/patients/${patientId}?book=1`, {
    waitUntil: "domcontentloaded",
  });

  await expect(page.getByTestId("patient-tabs")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("button", { name: "Book appointment" })).toHaveCount(0);
  await expect(page.getByTestId("patient-book-appointment")).toHaveCount(0);
  await expect(
    page.getByText("You do not have permission to create appointments.")
  ).toBeVisible();
});
