import { expect, test, type Page } from "@playwright/test";

import { getBaseUrl, primePageAuth } from "./helpers/auth";

async function waitForPatientSummary(page: Page, patientId: string) {
  await expect(page).toHaveURL(new RegExp(`/patients/${patientId}(?:\\?|$)`), {
    timeout: 20_000,
  });
  await expect(page.getByTestId("patient-tabs")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("patient-tab-Personal")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Loading patient…")).toHaveCount(0);
}

test("patient create shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const baseUrl = getBaseUrl();
  const firstName = `Stage163H Create ${unique}`;
  const lastName = `Proof ${unique}`;

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/new`, {
    waitUntil: "domcontentloaded",
  });

  const firstNameField = page.locator('label:has-text("First name") + input');
  const lastNameField = page.locator('label:has-text("Last name") + input');
  const submitButton = page.getByTestId("patient-create-submit");

  await expect(firstNameField).toBeVisible({ timeout: 15_000 });
  await expect(lastNameField).toBeVisible({ timeout: 15_000 });
  await expect(submitButton).toBeEnabled();

  await firstNameField.fill(firstName);
  await lastNameField.fill(lastName);

  const patientRoutePattern = /\/api\/patients$/;
  let requestCount = 0;
  let seenCreateRequest!: () => void;
  const seenCreateRequestPromise = new Promise<void>((resolve) => {
    seenCreateRequest = resolve;
  });
  let releaseCreateRequest!: () => void;
  const releaseCreateRequestPromise = new Promise<void>((resolve) => {
    releaseCreateRequest = resolve;
  });

  await page.route(patientRoutePattern, async (route) => {
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
      response.url().endsWith("/api/patients")
  );

  const clickState = await submitButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Patient create button not found");
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
    first_name: firstName,
    last_name: lastName,
  });
  const createdPatient = (await createResponse.json()) as { id: number };
  await page.unroute(patientRoutePattern);

  await waitForPatientSummary(page, String(createdPatient.id));
});
