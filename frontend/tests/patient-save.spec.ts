import { expect, test, type Page } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

async function waitForPatientPersonalTab(page: Page, patientId: string) {
  await expect(page).toHaveURL(new RegExp(`/patients/${patientId}(?:\\?|$)`));
  await expect(page.getByTestId("patient-tabs")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("patient-tab-Personal")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Loading patient…")).toHaveCount(0);
}

test("patient personal save shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `SAVE${unique}`,
  });
  const token = await primePageAuth(page, request);
  const updatedNotes = `Patient save proof ${unique}`;

  await page.goto(`${baseUrl}/patients/${patientId}`, {
    waitUntil: "domcontentloaded",
  });
  await waitForPatientPersonalTab(page, patientId);

  await page.getByTestId("patient-tab-Personal").click();
  await expect(page.getByTestId("patient-tab-Personal")).toHaveAttribute("aria-selected", "true");

  await page.getByText("Patient details", { exact: true }).click();
  const notesField = page.getByTestId("patient-notes-field");
  await expect(notesField).toBeVisible();
  await notesField.fill(updatedNotes);

  const saveButton = page.getByTestId("patient-save-changes");
  await expect(saveButton).toBeEnabled();

  let requestCount = 0;
  const patientRoutePattern = new RegExp(`/api/patients/${patientId}$`);
  let seenSaveRequest!: () => void;
  const seenSaveRequestPromise = new Promise<void>((resolve) => {
    seenSaveRequest = resolve;
  });
  let releaseSaveRequest!: () => void;
  const releaseSaveRequestPromise = new Promise<void>((resolve) => {
    releaseSaveRequest = resolve;
  });
  await page.route(patientRoutePattern, async (route) => {
    if (route.request().method() !== "PATCH") {
      await route.continue();
      return;
    }
    requestCount += 1;
    if (requestCount === 1) {
      seenSaveRequest();
      await releaseSaveRequestPromise;
    }
    await route.continue();
  });
  const saveResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      response.url().includes(`/api/patients/${patientId}`)
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
  await seenSaveRequestPromise;

  expect(clickState.beforeDisabled).toBe(false);
  expect(clickState.afterFirstDisabled).toBe(true);
  expect(clickState.afterSecondDisabled).toBe(true);
  await expect(saveButton).toBeDisabled();
  await expect(saveButton).toHaveText("Saving...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseSaveRequest();

  const saveResponse = await saveResponsePromise;
  expect(saveResponse.ok()).toBeTruthy();
  expect(saveResponse.request().postDataJSON()).toMatchObject({
    notes: updatedNotes,
  });
  await page.unroute(patientRoutePattern);

  await expect(saveButton).toHaveText("Save changes", { timeout: 15_000 });
  await expect(saveButton).toBeEnabled();

  const verifyResponse = await request.get(`${baseUrl}/api/patients/${patientId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(verifyResponse.ok()).toBeTruthy();
  const savedPatient = (await verifyResponse.json()) as { notes: string | null };
  expect(savedPatient.notes).toBe(updatedNotes);
});
