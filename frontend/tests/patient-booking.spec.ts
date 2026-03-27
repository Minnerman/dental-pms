import { expect, test, type Page } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

async function waitForPatientSummary(page: Page, patientId: string) {
  await expect(page).toHaveURL(new RegExp(`/patients/${patientId}(?:\\?|$)`));
  await expect(page.getByTestId("patient-tabs")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("patient-tab-Personal")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Loading patient…")).toHaveCount(0);
}

test("patient page Book appointment opens and scrolls the booking panel on summary tab", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `BOOKSCROLL${Date.now()}`,
  });

  await page.setViewportSize({ width: 1280, height: 640 });
  await primePageAuth(page, request);
  await page.goto(`${getBaseUrl()}/patients/${patientId}`, {
    waitUntil: "domcontentloaded",
  });
  await waitForPatientSummary(page, patientId);

  const scrollBeforeClick = await page.evaluate(() => Math.round(window.scrollY));
  const bookingCard = page.locator("#patient-book-appointment");

  await page.getByRole("button", { name: "Book appointment" }).click();

  await expect(bookingCard).toBeVisible({ timeout: 15_000 });
  await expect
    .poll(async () => page.evaluate(() => Math.round(window.scrollY)), {
      timeout: 15_000,
    })
    .toBeGreaterThan(scrollBeforeClick);
  await expect
    .poll(
      async () =>
        bookingCard.evaluate((node) => Math.round(node.getBoundingClientRect().top)),
      { timeout: 15_000 }
    )
    .toBeLessThanOrEqual(140);
});

test("patient page booking shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Stage163H",
    last_name: `BOOK${unique}`,
  });

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${patientId}`, {
    waitUntil: "domcontentloaded",
  });
  await waitForPatientSummary(page, patientId);

  await page.getByRole("button", { name: "Book appointment" }).click();

  const bookingCard = page.locator("#patient-book-appointment");
  await expect(bookingCard).toBeVisible();

  await bookingCard.getByTestId("patient-booking-date").fill("2026-03-20");
  await bookingCard.getByTestId("patient-booking-time").fill("09:00");
  await bookingCard.getByTestId("patient-booking-location").fill("Room 5");

  const submitButton = page.getByTestId("patient-booking-submit");
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
  const created = (await createResponse.json()) as { id: number };
  expect(createResponse.request().postDataJSON()).toMatchObject({
    patient_id: Number(patientId),
    location: "Room 5",
    location_type: "clinic",
  });
  await page.unroute(bookingRoutePattern);

  await expect(page).toHaveURL(new RegExp(`/appointments\\?date=2026-03-20&appointment=${created.id}$`), {
    timeout: 15_000,
  });
});
