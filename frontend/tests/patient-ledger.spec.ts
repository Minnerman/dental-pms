import { expect, test } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

test("patient ledger hides entry controls when payment capability is missing", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Ledger",
    last_name: `READONLY${Date.now()}`,
  });
  await primePageAuth(page, request);
  await page.route("**/api/me/capabilities", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(["billing.view"]),
    });
  });

  await page.goto(`${baseUrl}/patients/${patientId}`, { waitUntil: "domcontentloaded" });
  await page.getByTestId("patient-tab-Financial").click();
  await page.getByTestId("patient-financial-ledger").click();

  await expect(
    page.getByText("You can view this ledger, but you cannot add entries.")
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Add payment" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Add adjustment" })).toHaveCount(0);
});

test("patient ledger rejects sub-penny input and does not show a false zero balance", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Ledger",
    last_name: `VALIDATION${Date.now()}`,
  });
  await primePageAuth(page, request);

  await page.route(new RegExp(`/api/patients/${patientId}/balance(?:\\?|$)`), async (route) => {
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Service unavailable" }),
    });
  });
  let paymentRequests = 0;
  await page.route(new RegExp(`/api/patients/${patientId}/payments$`), async (route) => {
    if (route.request().method() === "POST") {
      paymentRequests += 1;
    }
    await route.continue();
  });

  await page.goto(`${baseUrl}/patients/${patientId}`, { waitUntil: "domcontentloaded" });
  await page.getByTestId("patient-tab-Financial").click();
  await page.getByTestId("patient-financial-ledger").click();
  await expect(page.getByTestId("patient-ledger-balance")).toContainText("unavailable");
  await expect(page.getByText("Service unavailable")).toBeVisible();

  await page.getByRole("button", { name: "Add payment" }).first().click();
  await page.getByPlaceholder("0.00").fill("0.001");
  await page.getByTestId("patient-ledger-save").click();

  await expect(
    page
      .getByText("Enter an amount greater than £0 with no more than two decimal places.")
      .first()
  ).toBeVisible();
  await page.waitForTimeout(200);
  expect(paymentRequests).toBe(0);
});
