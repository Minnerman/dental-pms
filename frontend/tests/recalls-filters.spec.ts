import { expect, test } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

test("recalls filters update worklist rows and export summary", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  const token = await ensureAuthReady(request);
  const unique = Date.now();
  const startDate = "2001-01-17";
  const endDate = "2001-01-18";

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
  const methodFilter = page.getByTestId("recalls-filter-method");
  const resetButton = page.getByTestId("recalls-reset-filters");
  const exportSummary = page.getByTestId("recalls-export-summary");

  const uncontactedRow = page.locator("table tbody tr").filter({ hasText: uncontactedNotes });
  const contactedRow = page.locator("table tbody tr").filter({ hasText: contactedNotes });

  await startDateFilter.fill(startDate);
  await endDateFilter.fill(endDate);

  await expect(uncontactedRow).toBeVisible({ timeout: 15_000 });
  await expect(contactedRow).toBeVisible({ timeout: 15_000 });
  await expect(exportSummary).toContainText("2 recalls", { timeout: 15_000 });

  await typeFilter.selectOption("hygiene");
  await expect(uncontactedRow).toHaveCount(0, { timeout: 15_000 });
  await expect(contactedRow).toBeVisible({ timeout: 15_000 });
  await expect(exportSummary).toContainText("1 recalls", { timeout: 15_000 });

  await contactStateFilter.selectOption("never");
  await expect(contactedRow).toHaveCount(0, { timeout: 15_000 });
  await expect(page.getByText("No recalls match your filters.")).toBeVisible({
    timeout: 15_000,
  });
  await expect(exportSummary).toContainText("0 recalls", { timeout: 15_000 });

  await contactStateFilter.selectOption("contacted");
  await expect(contactedRow).toBeVisible({ timeout: 15_000 });
  await expect(exportSummary).toContainText("1 recalls", { timeout: 15_000 });

  await methodFilter.selectOption("phone");
  await expect(contactedRow).toBeVisible({ timeout: 15_000 });
  await expect(exportSummary).toContainText("1 recalls", { timeout: 15_000 });

  await resetButton.click();
  await expect(typeFilter).toHaveValue("all");
  await expect(contactStateFilter).toHaveValue("all");
  await expect(methodFilter).toHaveValue("all");
  await expect(startDateFilter).toHaveValue("");
  await expect(endDateFilter).toHaveValue("");
  await expect(uncontactedRow).toBeVisible({ timeout: 15_000 });
  await expect(contactedRow).toBeVisible({ timeout: 15_000 });
});
