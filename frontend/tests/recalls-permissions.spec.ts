import { expect, test, type Page } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";


async function createRecall(
  page: Page,
  request: Parameters<typeof ensureAuthReady>[0],
  capabilities: string[]
) {
  const baseUrl = getBaseUrl();
  const token = await ensureAuthReady(request);
  const unique = Date.now();
  const patientId = await createPatient(request, {
    first_name: "Recall",
    last_name: `Permission ${unique}`,
  });
  const notes = `Synthetic recall permission ${unique}`;
  const response = await request.post(`${baseUrl}/api/patients/${patientId}/recalls`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      kind: "exam",
      due_date: new Date().toISOString().slice(0, 10),
      status: "due",
      notes,
    },
  });
  expect(response.ok()).toBeTruthy();
  const recall = (await response.json()) as { id: number };
  await primePageAuth(page, request);
  await page.route("**/api/me/capabilities", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(capabilities),
    });
  });
  return { patientId, recallId: recall.id, notes };
}


test("recall viewers get a deterministic read-only worklist", async ({ page, request }) => {
  const { notes } = await createRecall(page, request, ["recalls.view", "patients.view"]);
  await page.goto(`${getBaseUrl()}/recalls`, { waitUntil: "domcontentloaded" });

  const row = page.getByTestId("recalls-row").filter({ hasText: notes }).first();
  await expect(row).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("recalls-read-only-notice")).toBeVisible();
  await expect(row.getByTestId("recalls-patient-navigation")).toBeVisible();
  await expect(row.getByTestId("recalls-mutation-controls")).toHaveCount(0);
  await expect(row.getByTestId("recalls-book-action")).toHaveCount(0);
  await expect(page.getByTestId("recalls-export-csv")).toHaveCount(0);
  await expect(page.getByTestId("recalls-export-zip")).toHaveCount(0);
});


test("recall booking and export controls follow independent capabilities", async ({
  page,
  request,
}) => {
  const { notes } = await createRecall(page, request, [
    "recalls.view",
    "appointments.write",
  ]);
  await page.goto(`${getBaseUrl()}/recalls`, { waitUntil: "domcontentloaded" });

  let row = page.getByTestId("recalls-row").filter({ hasText: notes }).first();
  await expect(row).toBeVisible({ timeout: 15_000 });
  await expect(row.getByTestId("recalls-book-action")).toBeVisible();
  await expect(row.getByTestId("recalls-mutation-controls")).toHaveCount(0);
  await expect(page.getByTestId("recalls-export-csv")).toHaveCount(0);

  await page.unroute("**/api/me/capabilities");
  await page.route("**/api/me/capabilities", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(["recalls.view", "recalls.export"]),
    });
  });
  await page.reload({ waitUntil: "domcontentloaded" });

  row = page.getByTestId("recalls-row").filter({ hasText: notes }).first();
  await expect(row).toBeVisible({ timeout: 15_000 });
  await expect(row.getByTestId("recalls-book-action")).toHaveCount(0);
  await expect(row.getByTestId("recalls-mutation-controls")).toHaveCount(0);
  await expect(page.getByTestId("recalls-export-csv")).toBeVisible();
  await expect(page.getByTestId("recalls-export-zip")).toBeVisible();
});


test("patient recall controls respect read, write, and export permissions", async ({
  page,
  request,
}) => {
  const { patientId, notes } = await createRecall(page, request, [
    "patients.view",
    "recalls.view",
  ]);
  await page.goto(`${getBaseUrl()}/patients/${patientId}?tab=recalls`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("patient-tab-Schemes")).toHaveAttribute(
    "aria-selected",
    "true"
  );

  await expect(page.getByText(notes, { exact: true }).first()).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByTestId("patient-recall-entry-open")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Edit", exact: true }).first()).toBeDisabled();
  await expect(page.getByRole("button", { name: "Generate letter" }).first()).toBeDisabled();
  await expect(page.getByRole("button", { name: "Log contact" }).first()).toBeDisabled();
  await expect(page.getByRole("button", { name: "Mark completed" }).first()).toBeDisabled();
});


test("patient recall details stay hidden without recall view permission", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  const token = await ensureAuthReady(request);
  const patientId = await createPatient(request, {
    first_name: "Recall",
    last_name: `Redaction ${Date.now()}`,
  });
  const seeded = await request.post(`${baseUrl}/api/patients/${patientId}/recall`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      interval_months: 9,
      due_date: "2035-10-20",
      status: "booked",
      recall_type: "hygiene",
      notes: "synthetic restricted recall note",
    },
  });
  expect(seeded.ok()).toBeTruthy();

  await primePageAuth(page, request);
  await page.route("**/api/me/capabilities", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(["patients.view"]),
    });
  });
  const patientResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return response.request().method() === "GET" && url.pathname === `/api/patients/${patientId}`;
  });
  await page.goto(`${baseUrl}/patients/${patientId}`, {
    waitUntil: "domcontentloaded",
  });
  const patientResponse = await patientResponsePromise;
  const rawPatient = (await patientResponse.json()) as {
    recall_due_date: string | null;
    recall_status: string | null;
  };
  expect(rawPatient.recall_due_date).toBe("2035-10-20");
  expect(rawPatient.recall_status).toBe("booked");

  await expect(page.getByTestId("patient-header-card")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("patient-header-recall")).toHaveCount(0);
  await expect(page.getByTestId("patient-overview-recall-due")).toHaveCount(0);
  await expect(page.getByTestId("patient-overview-recall-status")).toHaveCount(0);
  await expect(page.getByTestId("patient-summary-recall")).toHaveCount(0);
  await expect(page.getByText("20/10/2035", { exact: true })).toHaveCount(0);
});


test("capability verification failure blocks recall data with a safe message", async ({
  page,
  request,
}) => {
  await primePageAuth(page, request);
  let recallListRequests = 0;
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (request.method() === "GET" && url.pathname === "/api/recalls") {
      recallListRequests += 1;
    }
  });
  await page.route("**/api/me/capabilities", async (route) => {
    await route.fulfill({
      status: 503,
      contentType: "text/html",
      body: "<html>private internal failure detail</html>",
    });
  });

  await page.goto(`${getBaseUrl()}/recalls`, { waitUntil: "domcontentloaded" });
  await expect(page.getByText("Recall permissions could not be verified.")).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText(/private internal failure detail/)).toHaveCount(0);
  expect(recallListRequests).toBe(0);
});


test("recall mutation failures never render raw backend responses", async ({
  page,
  request,
}) => {
  const { recallId, notes } = await createRecall(page, request, [
    "recalls.view",
    "recalls.write",
  ]);
  await page.route(new RegExp(`/api/patients/\\d+/recalls/${recallId}$`), async (route) => {
    if (route.request().method() !== "PATCH") {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 500,
      contentType: "text/html",
      body: "<html>private exception and infrastructure detail</html>",
    });
  });
  await page.goto(`${getBaseUrl()}/recalls`, { waitUntil: "domcontentloaded" });

  const row = page.getByTestId("recalls-row").filter({ hasText: notes }).first();
  await expect(row).toBeVisible({ timeout: 15_000 });
  await row.getByRole("button", { name: "Mark completed" }).click();
  await expect(page.getByText("Failed to update recall.")).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText(/private exception and infrastructure detail/)).toHaveCount(0);
});
