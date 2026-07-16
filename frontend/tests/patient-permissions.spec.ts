import { expect, test, type Page } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

async function mockCapabilities(page: Page, capabilities: string[]) {
  await page.route("**/api/me/capabilities", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(capabilities),
    });
  });
}

test("patient list and detail are read-only without patient write permission", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Permission",
    last_name: `Viewer ${Date.now()}`,
  });
  await primePageAuth(page, request);
  await mockCapabilities(page, ["patients.view"]);

  await page.goto(`${getBaseUrl()}/patients`, { waitUntil: "domcontentloaded" });
  await expect(page.getByText("You can view patients, but you cannot change them.")).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByRole("link", { name: "New patient" })).toHaveCount(0);

  await page.goto(`${getBaseUrl()}/patients/${patientId}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("patient-tabs")).toBeVisible({ timeout: 20_000 });
  await page.getByTestId("patient-tab-Personal").click();
  await page.getByText("Patient details", { exact: true }).click();

  await expect(page.getByText("You can view this patient, but you cannot change it.")).toBeVisible();
  await expect(page.getByTestId("patient-details-fields")).toHaveAttribute("disabled", "");
  await expect(page.getByTestId("patient-notes-field")).toBeDisabled();
  await expect(page.getByTestId("patient-save-changes")).toHaveCount(0);
  await expect(page.getByTestId("patient-archive-toggle")).toHaveCount(0);
});

test("new patient page blocks view-only users and validates names safely", async ({
  page,
  request,
}) => {
  await primePageAuth(page, request);
  await mockCapabilities(page, ["patients.view"]);
  await page.goto(`${getBaseUrl()}/patients/new`, { waitUntil: "domcontentloaded" });
  await expect(page.getByText("You do not have permission to create patients.")).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByTestId("patient-create-submit")).toHaveCount(0);

  await page.unroute("**/api/me/capabilities");
  await page.reload({ waitUntil: "domcontentloaded" });
  const firstName = page.locator('label:has-text("First name") + input');
  const lastName = page.locator('label:has-text("Last name") + input');
  await expect(firstName).toBeVisible({ timeout: 15_000 });
  await firstName.fill("   ");
  await lastName.fill("Validation");
  await page.getByTestId("patient-create-submit").click();
  await expect(page.getByText("First name and last name are required.")).toBeVisible();
  await expect(page).toHaveURL(/\/patients\/new$/);
});

test("archived patient state is explicit and only restore remains available", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Archived",
    last_name: `Patient ${Date.now()}`,
  });
  const token = await primePageAuth(page, request);
  const archived = await request.post(`${getBaseUrl()}/api/patients/${patientId}/archive`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(archived.ok()).toBeTruthy();

  await page.goto(`${getBaseUrl()}/patients/${patientId}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("patient-archived-badge")).toBeVisible({ timeout: 20_000 });
  await page.getByTestId("patient-tab-Personal").click();
  await page.getByText("Patient details", { exact: true }).click();
  await expect(page.getByText("Archived patient details are read-only until restored.")).toBeVisible();
  await expect(page.getByTestId("patient-details-fields")).toHaveAttribute("disabled", "");
  await expect(page.getByTestId("patient-notes-field")).toBeDisabled();
  await expect(page.getByTestId("patient-save-changes")).toHaveCount(0);
  await expect(page.getByTestId("patient-archive-toggle")).toHaveText("Restore patient");
});
