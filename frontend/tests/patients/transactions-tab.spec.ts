import { expect, test } from "@playwright/test";

import { createPatient } from "../helpers/api";
import { getBaseUrl, primePageAuth } from "../helpers/auth";

test("patient transactions tab renders, paginates, and filters", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Tx",
    last_name: `Playwright ${Date.now()}`,
  });

  const pageOne = [
    {
      legacy_transaction_id: 101,
      performed_at: "2026-01-20T10:00:00Z",
      treatment_code: 12,
      treatment_name: "Comprehensive exam",
      trans_code: 5,
      patient_cost: 45.0,
      dpb_cost: 0.0,
      recorded_by: 2,
      user_code: 12,
      recorded_by_name: "Dr Ada Lovelace",
      user_name: "Mr Sam Clerk",
      recorded_by_is_current: true,
      user_is_current: false,
      recorded_by_role: "Dentist",
      user_role: "Nurse",
    },
    {
      legacy_transaction_id: 100,
      performed_at: "2026-01-19T09:00:00Z",
      treatment_code: 10,
      treatment_name: null,
      trans_code: 3,
      patient_cost: 0.0,
      dpb_cost: 20.0,
      recorded_by: 2,
      user_code: 12,
      recorded_by_name: "Dr Ada Lovelace",
      user_name: "Mr Sam Clerk",
      recorded_by_is_current: true,
      user_is_current: false,
      recorded_by_role: "Dentist",
      user_role: null,
    },
  ];
  const pageTwo = [
    {
      legacy_transaction_id: 99,
      performed_at: "2026-01-18T08:00:00Z",
      treatment_code: 8,
      treatment_name: "Fluoride varnish",
      trans_code: 2,
      patient_cost: 15.0,
      dpb_cost: 0.0,
      recorded_by: 3,
      user_code: 14,
      recorded_by_name: "Dr Ada Lovelace",
      user_name: "Mr Sam Clerk",
      recorded_by_is_current: null,
      user_is_current: true,
      recorded_by_role: null,
      user_role: "Hygienist",
    },
  ];

  type TransactionsPayload = {
    items: Array<{
      legacy_transaction_id: number;
      performed_at: string;
      treatment_code: number | null;
      treatment_name?: string | null;
      trans_code: number | null;
      patient_cost: number | null;
      dpb_cost: number | null;
      recorded_by: number | null;
      user_code: number | null;
      recorded_by_name?: string | null;
      user_name?: string | null;
      recorded_by_is_current?: boolean | null;
      user_is_current?: boolean | null;
      recorded_by_role?: string | null;
      user_role?: string | null;
    }>;
    next_cursor: string | null;
  };

  await page.route(`**/api/patients/${patientId}/treatment-transactions**`, async (route) => {
    const url = new URL(route.request().url());
    const cursor = url.searchParams.get("cursor");
    const costOnly = url.searchParams.get("cost_only") === "true";
    const from = url.searchParams.get("from");
    const to = url.searchParams.get("to");

    let payload: TransactionsPayload;
    if (from === "2026-01-01" && to === "2026-01-01") {
      payload = { items: [], next_cursor: null };
    } else if (costOnly) {
      payload = { items: [pageOne[0]], next_cursor: null };
    } else if (cursor === "cursor-1") {
      await new Promise((resolve) => setTimeout(resolve, 200));
      payload = { items: pageTwo, next_cursor: null };
    } else {
      payload = { items: pageOne, next_cursor: "cursor-1" };
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(payload),
    });
  });

  await primePageAuth(page, request);
  await page.goto(`${getBaseUrl()}/patients/${patientId}`, { waitUntil: "domcontentloaded" });

  await page.getByTestId("patient-tab-Appointments").click();

  const table = page.getByTestId("transactions-table");
  const empty = page.getByTestId("transactions-empty");
  await Promise.race([table.waitFor({ state: "visible" }), empty.waitFor({ state: "visible" })]);
  await expect(table).toBeVisible();

  const rows = table.locator("tbody tr");
  await expect(rows).toHaveCount(2);
  await expect(table).toContainText("Dr Ada Lovelace");
  await expect(table).toContainText("Dentist");
  await expect(table).toContainText("Current");
  await expect(table).toContainText("Comprehensive exam");

  const loadMore = page.getByTestId("transactions-load-more");
  await expect(loadMore).toBeVisible();
  await loadMore.click();
  await expect(page.getByTestId("transactions-loading-row")).toBeVisible();
  await expect(rows).toHaveCount(3);

  await page.getByTestId("transactions-filter-cost-only").locator("input").check();
  await page.getByTestId("transactions-apply-filters").click();
  await expect(page).toHaveURL(/tx_cost=1/);
  await expect(rows).toHaveCount(1);

  await page.getByTestId("transactions-filter-cost-only").locator("input").uncheck();
  await page.getByTestId("transactions-filter-from").fill("2026-01-01");
  await page.getByTestId("transactions-filter-to").fill("2026-01-01");
  await page.getByTestId("transactions-apply-filters").click();
  await expect(page).toHaveURL(/tx_from=2026-01-01/);
  await expect(page.getByTestId("transactions-empty")).toBeVisible();

  await page.getByTestId("transactions-reset-filters").click();
  await expect(page).not.toHaveURL(/tx_from=|tx_to=|tx_cost=/);
});
