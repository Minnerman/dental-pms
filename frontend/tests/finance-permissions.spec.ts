import { expect, test } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";


test("patient finance waits for and enforces billing.view", async ({ page, request }) => {
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(request, {
    first_name: "Finance",
    last_name: `RESTRICTED${Date.now()}`,
  });
  await primePageAuth(page, request);

  let financeReads = 0;
  await page.route("**/api/me/capabilities", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(["patients.view"]),
    });
  });
  await page.route(new RegExp(`/api/(patients/${patientId}/(?:ledger|balance|finance-summary)|invoices)`), async (route) => {
    financeReads += 1;
    await route.continue();
  });

  await page.goto(`${baseUrl}/patients/${patientId}`, { waitUntil: "domcontentloaded" });

  await expect(page.getByTestId("patient-tab-Financial")).toBeDisabled();
  await expect(page.getByText("You do not have permission to view billing information.")).toBeVisible();
  await page.waitForTimeout(200);
  expect(financeReads).toBe(0);
});


test("cash-up and reports do not read finance data without both report capabilities", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  await primePageAuth(page, request);

  let reportReads = 0;
  await page.route("**/api/me/capabilities", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(["billing.view"]),
    });
  });
  await page.route("**/api/reports/**", async (route) => {
    reportReads += 1;
    await route.continue();
  });

  await page.goto(`${baseUrl}/cashup`, { waitUntil: "domcontentloaded" });
  await expect(page.getByText("You do not have permission to view cash-up reports.")).toBeVisible();
  await page.goto(`${baseUrl}/reports`, { waitUntil: "domcontentloaded" });
  await expect(page.getByText("You do not have permission to view financial reports.")).toBeVisible();
  await page.waitForTimeout(200);
  expect(reportReads).toBe(0);
});
