import { expect, test, type Page } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

const directoryPath = "/api/patients/directory";
const directoryCapabilities = ["patients.view", "patients.write", "billing.view", "appointments.view"];

type DirectoryRow = {
  id: number; first_name: string; last_name: string; phone: string | null;
  date_of_birth: string | null; patient_category: string; created_at: string;
  updated_at: string; deleted_at: string | null; balance_pence: number | null;
  last_visit_at: string | null;
};

function exampleRows(): DirectoryRow[] {
  return [
    { id: 91001, first_name: "Synthetic Alex", last_name: "Example", phone: "07700 900123", date_of_birth: "1980-05-03", patient_category: "CLINIC_PRIVATE", created_at: "2026-08-01T09:00:00Z", updated_at: "2026-09-05T09:00:00Z", deleted_at: null, balance_pence: 5000, last_visit_at: "2026-08-31T10:00:00Z" },
    { id: 91002, first_name: "Synthetic Jamie", last_name: "Sample", phone: null, date_of_birth: null, patient_category: "DOMICILIARY_PRIVATE", created_at: "2026-08-02T09:00:00Z", updated_at: "2026-09-04T09:00:00Z", deleted_at: null, balance_pence: -500, last_visit_at: null },
    { id: 91003, first_name: "Synthetic Casey", last_name: "Zero", phone: null, date_of_birth: "1990-04-12", patient_category: "DENPLAN", created_at: "2026-08-03T09:00:00Z", updated_at: "2026-09-03T09:00:00Z", deleted_at: null, balance_pence: 0, last_visit_at: null },
  ];
}

function directoryFixture(items = exampleRows(), total = items.length, offset = 0) {
  return {
    items, total, limit: 50, offset,
    metadata: { finance: "available", last_visit: "available", do_not_contact: "unavailable" },
    definitions: {
      finance: "Positive native patient ledger balances are due; negative balances are credit.",
      last_visit: "Latest completed native appointment; not a planned appointment or record edit.",
      do_not_contact: "Contact preferences are not recorded yet.",
    },
  };
}

async function mockCapabilities(page: Page, values = directoryCapabilities) {
  await page.route("**/api/me/capabilities", (route) => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify(values),
  }));
}

async function mockDirectory(page: Page, payload: unknown = directoryFixture()) {
  await page.route(`**${directoryPath}*`, (route) => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify(payload),
  }));
}

async function openDirectory(page: Page) {
  await page.goto(`${getBaseUrl()}/patients`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("patients-directory")).toBeVisible({ timeout: 20_000 });
}

function nextDirectoryResponse(page: Page, expected: Record<string, string>) {
  return page.waitForResponse((response) => {
    const url = new URL(response.url());
    return response.request().method() === "GET" && url.pathname === directoryPath &&
      Object.entries(expected).every(([key, value]) => url.searchParams.get(key) === value);
  });
}

test("compact directory rows show last-name-first identity, contact and truthful financial and visit summaries", async ({ page, request }) => {
  await primePageAuth(page, request);
  await mockCapabilities(page);
  await mockDirectory(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await openDirectory(page);
  const first = page.getByTestId("patient-directory-row-91001");
  await expect(first).toBeVisible();
  await expect(first).toContainText("Example, Synthetic Alex");
  await expect(first).toContainText("07700 900123");
  await expect(first).toContainText("Due £50.00");
  await expect(first).toContainText(/Last visit/i);
  await expect(first.getByRole("link", { name: "Synthetic Alex Example", exact: true })).toHaveAttribute("href", "/patients/91001");
  expect((await first.boundingBox())!.height).toBeLessThanOrEqual(112);
  await expect(page.getByTestId("patient-directory-row-91002")).toContainText("Credit £5.00");
  await expect(page.getByTestId("patient-directory-row-91002")).toContainText("No recorded visit");
  await expect(page.getByTestId("patient-directory-row-91003")).not.toContainText("£0");
  await expect(page.getByTestId("patients-directory-list")).not.toContainText(/Created by|Updated by/);
  await expect(page.getByRole("button", { name: "Do not contact", exact: true })).toBeDisabled();
  await expect(page.getByText("Contact preferences are not recorded yet.", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("link", { name: "New patient", exact: true })).toHaveAttribute("href", "/patients/new");
});

test("search, status, debt and sort controls send the selected server filters", async ({ page, request }) => {
  await primePageAuth(page, request);
  await mockCapabilities(page);
  await mockDirectory(page);
  await openDirectory(page);
  await expect(page.getByTestId("patient-directory-row-91001")).toBeVisible();
  const search = nextDirectoryResponse(page, { query: "Synthetic", offset: "0" });
  await page.getByPlaceholder("Search name, email, phone").fill("Synthetic");
  await search;
  await page.getByRole("button", { name: "Clear search", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByPlaceholder("Search name, email, phone")).toBeFocused();
  await expect(page.getByPlaceholder("Search name, email, phone")).toHaveValue("");
  const sort = nextDirectoryResponse(page, { sort: "joined", direction: "desc", offset: "0" });
  await page.getByRole("combobox", { name: "Sort patients", exact: true }).selectOption("joined");
  await sort;
  const ascending = nextDirectoryResponse(page, { sort: "joined", direction: "asc", offset: "0" });
  await page.getByRole("button", { name: "Sort ascending", exact: true }).click();
  await ascending;
  await page.getByRole("button", { name: "Filters", exact: true }).click();
  const status = nextDirectoryResponse(page, { status: "archived", offset: "0" });
  await page.getByRole("combobox", { name: "Patient status", exact: true }).selectOption("archived");
  await status;
  const debt = nextDirectoryResponse(page, { with_debt: "true", offset: "0" });
  await page.getByRole("button", { name: "With debt", exact: true }).click();
  await debt;
});

test("pagination loads the requested page and changing a filter returns to the first page", async ({ page, request }) => {
  await primePageAuth(page, request);
  await mockCapabilities(page);
  const rows = Array.from({ length: 52 }, (_, index) => ({ ...exampleRows()[0], id: 92000 + index, first_name: `Synthetic ${index + 1}`, last_name: "Paged", balance_pence: 0, phone: null }));
  await page.route(`**${directoryPath}*`, (route) => {
    const offset = Number(new URL(route.request().url()).searchParams.get("offset") ?? 0);
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(directoryFixture(rows.slice(offset, offset + 50), rows.length, offset)) });
  });
  await openDirectory(page);
  await expect(page.getByTestId("patient-directory-row-92000")).toBeVisible();
  await expect(page.getByRole("button", { name: "Previous page", exact: true })).toBeDisabled();
  const secondPage = nextDirectoryResponse(page, { offset: "50", limit: "50" });
  await page.getByRole("button", { name: "Next page", exact: true }).focus();
  await page.keyboard.press("Enter");
  await secondPage;
  await expect(page.getByTestId("patient-directory-row-92050")).toBeVisible();
  await expect(page.getByTestId("patient-directory-row-92050").getByRole("link")).toBeFocused();
  await expect(page.getByTestId("patient-directory-row-92000")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Next page", exact: true })).toBeDisabled();
  const reset = nextDirectoryResponse(page, { offset: "0", query: "Paged" });
  await page.getByPlaceholder("Search name, email, phone").fill("Paged");
  await reset;
  await expect(page.getByTestId("patient-directory-row-92000")).toBeVisible();
  await expect(page.getByRole("button", { name: "Previous page", exact: true })).toBeDisabled();
});

test("restricted finance and visit permissions do not become zero balances or invented visit histories", async ({ page, request }) => {
  await primePageAuth(page, request);
  await mockCapabilities(page, ["patients.view"]);
  const fixture = directoryFixture();
  await mockDirectory(page, {
    ...fixture,
    items: fixture.items.map((row) => ({ ...row, balance_pence: null, last_visit_at: null })),
    metadata: { finance: "forbidden", last_visit: "forbidden", do_not_contact: "unavailable" },
  });
  await openDirectory(page);
  const first = page.getByTestId("patient-directory-row-91001");
  await expect(first).toBeVisible();
  await expect(first).not.toContainText(/£|Last visit|No recorded visit/);
  await expect(page.getByRole("button", { name: "With debt", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Do not contact", exact: true })).toBeDisabled();
  await expect(page.getByRole("combobox", { name: "Sort patients", exact: true }).locator('option[value="last_visit"]')).toBeDisabled();
  await expect(page.getByRole("link", { name: "New patient", exact: true })).toHaveCount(0);
});

for (const failure of ["denied", "unverified"] as const) {
  test(`directory does not request patient data when access is ${failure}`, async ({ page, request }) => {
    await primePageAuth(page, request);
    await page.route("**/api/me/capabilities", (route) => route.fulfill(failure === "denied"
      ? { status: 200, contentType: "application/json", body: JSON.stringify(["appointments.view"]) }
      : { status: 503, contentType: "text/html", body: "<html>private patient permissions response</html>" }));
    let calls = 0;
    await page.route(`**${directoryPath}*`, (route) => { calls += 1; return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(directoryFixture()) }); });
    await openDirectory(page);
    await expect(page.getByTestId("patients-directory-error")).toBeVisible();
    await expect(page.getByTestId("patients-directory-list")).toHaveCount(0);
    await expect(page.getByTestId("patients-directory")).not.toContainText("Synthetic Alex");
    await expect(page.getByTestId("patients-directory")).not.toContainText("private patient permissions response");
    expect(calls).toBe(0);
  });
}

test("loading and failed directory requests do not show a false empty list, and Retry recovers", async ({ page, request }) => {
  await primePageAuth(page, request);
  await mockCapabilities(page);
  let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  let seenRequest!: () => void;
  const requested = new Promise<void>((resolve) => { seenRequest = resolve; });
  let ready = false;
  await page.route(`**${directoryPath}*`, async (route) => {
    seenRequest();
    if (!ready) {
      await gate;
      return route.fulfill({ status: 503, contentType: "text/html", body: "<html>private patient directory response</html>" });
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(directoryFixture([])) });
  });
  await openDirectory(page);
  await requested;
  await expect(page.getByText("Loading patients…", { exact: false })).toBeVisible();
  await expect(page.getByTestId("patients-directory-empty")).toHaveCount(0);
  await expect(page.getByTestId("patient-directory-row-91001")).toHaveCount(0);
  release();
  await expect(page.getByTestId("patients-directory-error")).toBeVisible();
  await expect(page.getByTestId("patients-directory-empty")).toHaveCount(0);
  await expect(page.getByTestId("patients-directory")).not.toContainText("private patient directory response");
  ready = true;
  await page.getByTestId("patients-directory-error").getByRole("button", { name: /retry/i }).click();
  await expect(page.getByTestId("patients-directory-empty")).toBeVisible();
  await expect(page.getByTestId("patients-directory-error")).toHaveCount(0);
});

test("directory keeps compact rows readable in light, dark and narrow layouts", async ({ page, request }, testInfo) => {
  await primePageAuth(page, request);
  await mockCapabilities(page);
  await mockDirectory(page);
  await page.route("**/api/me", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id: 91000, email: "synthetic.operator@example.com", full_name: "Synthetic operator", role: "superadmin", is_active: true, must_change_password: false }) }));
  await page.setViewportSize({ width: 1440, height: 1000 });
  await openDirectory(page);
  await expect(page.getByTestId("patient-directory-row-91001")).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("patients-directory-light.png"), fullPage: true });
  await page.getByRole("button", { name: "Toggle theme", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.screenshot({ path: testInfo.outputPath("patients-directory-dark.png"), fullPage: true });
  await page.setViewportSize({ width: 950, height: 844 });
  await page.getByRole("button", { name: "Filters", exact: true }).click();
  const filters = page.getByRole("group", { name: "Patient filters", exact: true });
  await expect(filters).toBeVisible();
  await expect.poll(() => filters.evaluate((element) => {
    const box = element.getBoundingClientRect();
    return box.left >= 0 && box.right <= window.innerWidth + 1;
  })).toBe(true);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("patients-directory-filters-950-dark.png"), fullPage: true });
  await page.keyboard.press("Escape");
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.getByRole("button", { name: "Toggle theme", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.screenshot({ path: testInfo.outputPath("patients-directory-1280-light.png"), fullPage: true });
  await page.getByRole("button", { name: "Toggle theme", exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await expect(page.getByTestId("patient-directory-row-91001")).toBeVisible();
  await expect(page.getByTestId("patient-directory-row-91003")).toBeVisible();
  await expect(page.getByTestId("patient-directory-row-91001").getByText("DOB 3 May 1980", { exact: true }).first()).toBeVisible();
  await expect(page.getByTestId("patient-directory-row-91002").getByText("Patient #91002", { exact: true })).toBeVisible();
  await expect(page.getByTestId("patient-directory-row-91001").getByRole("link")).toHaveAccessibleDescription(/Patient #91001.*Date of birth 3 May 1980.*Phone 07700 900123/);
  await page.screenshot({ path: testInfo.outputPath("patients-directory-mobile-dark.png"), fullPage: true });
});

test("real directory API and browser agree on a synthetic patient balance and completed last visit", async ({ page, request }) => {
  const unique = Date.now();
  const firstName = "Synthetic Directory";
  const lastName = `LedgerVisit${unique}`;
  const patientId = await createPatient(request, { first_name: firstName, last_name: lastName });
  const token = await ensureAuthReady(request);
  const headers = { Authorization: `Bearer ${token}` };
  const charge = await request.post(`${getBaseUrl()}/api/patients/${patientId}/charges`, {
    headers, data: { amount_pence: 10000, note: "Synthetic directory test charge" },
  });
  expect(charge.ok()).toBeTruthy();
  const payment = await request.post(`${getBaseUrl()}/api/patients/${patientId}/payments`, {
    headers, data: { amount_pence: 2500, method: "card", note: "Synthetic directory test payment" },
  });
  expect(payment.ok()).toBeTruthy();
  const visitStart = "2026-08-20T09:00:00.000Z";
  const visit = await request.post(`${getBaseUrl()}/api/appointments`, {
    headers, data: {
      patient_id: Number(patientId), clinician_user_id: null,
      starts_at: visitStart, ends_at: "2026-08-20T09:30:00.000Z",
      status: "completed", location_type: "clinic", location: `Synthetic room ${unique}`,
    },
  });
  expect(visit.ok()).toBeTruthy();
  const directory = await request.get(`${getBaseUrl()}${directoryPath}`, {
    headers, params: { query: lastName },
  });
  expect(directory.ok()).toBeTruthy();
  const data = await directory.json();
  expect(data.items).toHaveLength(1);
  expect(data.items[0].id).toBe(Number(patientId));
  expect(data.items[0].balance_pence).toBe(7500);
  expect(new Date(data.items[0].last_visit_at).toISOString()).toBe(visitStart);
  await primePageAuth(page, request);
  await openDirectory(page);
  const searched = nextDirectoryResponse(page, { query: lastName, offset: "0" });
  await page.getByPlaceholder("Search name, email, phone").fill(lastName);
  await searched;
  const row = page.getByTestId(`patient-directory-row-${patientId}`);
  await expect(row).toContainText(`${lastName}, ${firstName}`);
  await expect(row).toContainText("Due £75.00");
  await expect(row).toContainText("Last visit 20 Aug 2026");
  await page.getByRole("link", { name: "New patient", exact: true }).click();
  await expect(page).toHaveURL(/\/patients\/new$/);
  await expect(page.getByRole("heading", { name: "New patient", exact: true })).toBeVisible();
});
