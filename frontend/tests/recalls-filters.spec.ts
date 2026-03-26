import { expect, test, type APIRequestContext } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

type ExportCountResponse = {
  count: number;
};

function addDays(value: string, days: number) {
  const next = new Date(`${value}T00:00:00.000Z`);
  next.setUTCDate(next.getUTCDate() + days);
  return next.toISOString().slice(0, 10);
}

function buildFilterParams(entries: Record<string, string | null | undefined>) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(entries)) {
    if (!value) continue;
    params.set(key, value);
  }
  return params;
}

async function fetchExportCount(
  request: APIRequestContext,
  baseUrl: string,
  token: string,
  params: URLSearchParams
) {
  const response = await request.get(`${baseUrl}/api/recalls/export_count?${params.toString()}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(response.ok()).toBeTruthy();
  const payload = (await response.json()) as ExportCountResponse;
  return payload.count;
}

test("recalls filters update worklist rows, summary count, and reset state", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  const token = await ensureAuthReady(request);
  const unique = Date.now();
  const year = 2050 + (unique % 30);
  const month = String((unique % 12) + 1).padStart(2, "0");
  const day = String((unique % 20) + 1).padStart(2, "0");
  const startDate = `${year}-${month}-${day}`;
  const endDate = addDays(startDate, 1);

  const uncontactedPatientId = await createPatient(request, {
    first_name: "Recall",
    last_name: `Filter Due ${unique}`,
  });
  const contactedPatientId = await createPatient(request, {
    first_name: "Recall",
    last_name: `Filter Contacted ${unique}`,
  });

  const uncontactedNotes = `Recalls filters exam ${unique}`;
  const contactedNotes = `Recalls filters hygiene ${unique}`;

  const uncontactedRecallResponse = await request.post(
    `${baseUrl}/api/patients/${uncontactedPatientId}/recalls`,
    {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        kind: "exam",
        due_date: startDate,
        status: "due",
        notes: uncontactedNotes,
      },
    }
  );
  expect(uncontactedRecallResponse.ok()).toBeTruthy();

  const contactedRecallResponse = await request.post(
    `${baseUrl}/api/patients/${contactedPatientId}/recalls`,
    {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        kind: "hygiene",
        due_date: endDate,
        status: "due",
        notes: contactedNotes,
      },
    }
  );
  expect(contactedRecallResponse.ok()).toBeTruthy();
  const contactedRecall = (await contactedRecallResponse.json()) as { id: number };

  const contactResponse = await request.post(
    `${baseUrl}/api/recalls/${contactedRecall.id}/contact`,
    {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        method: "phone",
        other_detail: null,
        outcome: `Reached patient ${unique}`,
        note: `Recalls filters phone contact ${unique}`,
      },
    }
  );
  expect(contactResponse.ok()).toBeTruthy();

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/recalls`, { waitUntil: "domcontentloaded" });

  const startDateFilter = page.getByTestId("recalls-filter-start-date");
  const endDateFilter = page.getByTestId("recalls-filter-end-date");
  const typeFilter = page.getByTestId("recalls-filter-type");
  const contactStateFilter = page.getByTestId("recalls-filter-contact-state");
  const lastContactFilter = page.getByTestId("recalls-filter-last-contact");
  const methodFilter = page.getByTestId("recalls-filter-method");
  const resetButton = page.getByTestId("recalls-reset-filters");
  const exportSummary = page.getByTestId("recalls-export-summary");
  const pageSize = page.getByLabel("Per page");

  const uncontactedRow = page.locator("table tbody tr").filter({ hasText: uncontactedNotes });
  const contactedRow = page.locator("table tbody tr").filter({ hasText: contactedNotes });

  await pageSize.selectOption("200");
  await expect(pageSize).toHaveValue("200");
  await startDateFilter.fill(startDate);
  await endDateFilter.fill(endDate);

  const baseParams = buildFilterParams({
    status: "due,overdue",
    start: startDate,
    end: endDate,
  });
  const allCount = await fetchExportCount(request, baseUrl, token, baseParams);

  await expect(uncontactedRow).toBeVisible({ timeout: 15_000 });
  await expect(contactedRow).toBeVisible({ timeout: 15_000 });
  await expect(exportSummary).toContainText(`${allCount} recalls`, { timeout: 15_000 });

  await typeFilter.selectOption("hygiene");
  const hygieneParams = buildFilterParams({
    status: "due,overdue",
    start: startDate,
    end: endDate,
    type: "hygiene",
  });
  const hygieneCount = await fetchExportCount(request, baseUrl, token, hygieneParams);
  await expect(uncontactedRow).toHaveCount(0, { timeout: 15_000 });
  await expect(contactedRow).toBeVisible({ timeout: 15_000 });
  await expect(exportSummary).toContainText(`${hygieneCount} recalls`, { timeout: 15_000 });

  await contactStateFilter.selectOption("contacted");
  const contactedParams = buildFilterParams({
    status: "due,overdue",
    start: startDate,
    end: endDate,
    type: "hygiene",
    contact_state: "contacted",
  });
  const contactedCount = await fetchExportCount(request, baseUrl, token, contactedParams);
  await expect(contactedRow).toBeVisible({ timeout: 15_000 });
  await expect(exportSummary).toContainText(`${contactedCount} recalls`, { timeout: 15_000 });

  await lastContactFilter.selectOption("7d");
  const recentContactParams = buildFilterParams({
    status: "due,overdue",
    start: startDate,
    end: endDate,
    type: "hygiene",
    contact_state: "contacted",
    last_contact: "7d",
  });
  const recentContactCount = await fetchExportCount(request, baseUrl, token, recentContactParams);
  await expect(contactedRow).toBeVisible({ timeout: 15_000 });
  await expect(exportSummary).toContainText(`${recentContactCount} recalls`, {
    timeout: 15_000,
  });

  await methodFilter.selectOption("phone");
  const phoneParams = buildFilterParams({
    status: "due,overdue",
    start: startDate,
    end: endDate,
    type: "hygiene",
    contact_state: "contacted",
    last_contact: "7d",
    method: "phone",
  });
  const phoneCount = await fetchExportCount(request, baseUrl, token, phoneParams);
  await expect(contactedRow).toBeVisible({ timeout: 15_000 });
  await expect(exportSummary).toContainText(`${phoneCount} recalls`, { timeout: 15_000 });

  await contactStateFilter.selectOption("never");
  const impossibleParams = buildFilterParams({
    status: "due,overdue",
    start: startDate,
    end: endDate,
    type: "hygiene",
    contact_state: "never",
    last_contact: "7d",
    method: "phone",
  });
  const impossibleCount = await fetchExportCount(request, baseUrl, token, impossibleParams);
  expect(impossibleCount).toBe(0);
  await expect(uncontactedRow).toHaveCount(0, { timeout: 15_000 });
  await expect(contactedRow).toHaveCount(0, { timeout: 15_000 });
  await expect(page.getByText("No recalls match your filters.")).toBeVisible({
    timeout: 15_000,
  });
  await expect(exportSummary).toContainText("0 recalls", { timeout: 15_000 });

  await resetButton.click();
  await expect(typeFilter).toHaveValue("all");
  await expect(contactStateFilter).toHaveValue("all");
  await expect(lastContactFilter).toHaveValue("all");
  await expect(methodFilter).toHaveValue("all");
  await expect(startDateFilter).toHaveValue("");
  await expect(endDateFilter).toHaveValue("");
  const resetParams = buildFilterParams({
    status: "due,overdue",
  });
  const resetCount = await fetchExportCount(request, baseUrl, token, resetParams);
  await expect(uncontactedRow).toBeVisible({ timeout: 15_000 });
  await expect(contactedRow).toBeVisible({ timeout: 15_000 });
  await expect(exportSummary).toContainText(`${resetCount} recalls`, { timeout: 15_000 });
});
