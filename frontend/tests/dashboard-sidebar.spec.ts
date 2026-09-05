import { expect, test, type Page } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

const dashboardPath = "/api/dashboard/home";

function dashboardFixture() {
  return {
    generated_at: "2026-09-05T08:30:00Z",
    date: "2026-09-05",
    timezone: "Europe/London",
    currency: "GBP",
    periods: {
      current_start: "2026-08-30", current_end: "2026-09-05",
      previous_start: "2026-08-23", previous_end: "2026-08-29",
      week_start: "2026-08-31", week_end: "2026-09-06",
      month_start: "2026-09-01", month_end: "2026-09-30",
    },
    appointments: {
      availability: "available", today_count: 2, in_clinic_count: 1,
      schedule_availability: "available",
      schedule: [
        { id: 90001, patient_id: 90001, patient_name: "Synthetic Alex Demo", starts_at: "2026-09-05T09:00:00Z", ends_at: "2026-09-05T09:30:00Z", status: "arrived", appointment_type: "Examination", clinician: "Synthetic clinician", location_type: "clinic" },
        { id: 90002, patient_id: 90002, patient_name: "Synthetic Jamie Demo", starts_at: "2026-09-05T10:00:00Z", ends_at: "2026-09-05T10:45:00Z", status: "booked", appointment_type: "Review", clinician: "Synthetic clinician", location_type: "visit" },
      ],
      schedule_has_more: false,
      unconfirmed_tomorrow: { availability: "unavailable", value: null, reason: "confirmation_not_recorded" },
      last_7_days: { appointments: 8, completed: 6, completion_rate: 75 },
      previous_7_days: { appointments: 10, completed: 5, completion_rate: 50 },
    },
    payments: {
      availability: "available", overdue_invoice_count: 3, overdue_balance_pence: 12750,
      items_availability: "available",
      items: [{ invoice_id: 90001, invoice_number: "DEMO-90001", patient_id: 90001, patient_name: "Synthetic Alex Demo", due_date: "2026-08-30", balance_pence: 12750 }],
      items_has_more: false,
      last_7_days_invoiced_pence: 40000, previous_7_days_invoiced_pence: 30000,
    },
    patients: {
      availability: "available",
      recent: [
        { id: 90001, name: "Synthetic Alex Demo", phone: "07700 900123", created_at: "2026-09-04T10:00:00Z" },
        { id: 90002, name: "Synthetic Jamie Demo", phone: null, created_at: "2026-09-03T11:00:00Z" },
      ],
      recent_has_more: false, basis: "created_at",
    },
    recalls: {
      availability: "available", due_this_week: 4, overdue: 2, scheduled_this_month: 5,
      conversion_rate: { availability: "unavailable", value: null, reason: "conversion_not_recorded" },
    },
    definitions: {
      in_clinic: "Clinic appointments marked arrived or in progress today.",
      recent_patients: "Recently created patient records; not recently viewed patients.",
      unconfirmed_tomorrow: "Appointment confirmation is not recorded.",
      recall_conversion: "Recall conversion is not recorded.",
    },
  };
}

async function mockDashboard(page: Page, payload: unknown = dashboardFixture()) {
  await page.route(`**${dashboardPath}`, (route) => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify(payload),
  }));
}

async function mockSyntheticOperator(page: Page) {
  await page.route("**/api/me", (route) => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({ id: 90000, email: "demo.operator@example.com", full_name: "Synthetic operator", role: "superadmin", is_active: true, must_change_password: false }),
  }));
}

async function openDashboard(page: Page) {
  await page.goto(`${getBaseUrl()}/`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("dashboard-root")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("dashboard-value-today-appointments")).toBeVisible({ timeout: 20_000 });
}

async function expectDocumentFits(page: Page) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
}

test("signed-out root opens a blank sign-in form, successful login opens Home, and sign-out locks Home", async ({ page, request }, testInfo) => {
  await ensureAuthReady(request);
  let dashboardRequests = 0;
  await page.route(`**${dashboardPath}`, (route) => {
    dashboardRequests += 1;
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(dashboardFixture()) });
  });
  await page.goto(`${getBaseUrl()}/`, { waitUntil: "domcontentloaded" });
  await expect(page).toHaveURL(/\/login(?:[?#]|$)/, { timeout: 20_000 });
  await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeVisible();
  await expect(page.locator("#login-email")).toHaveValue("");
  await expect(page.locator("#login-password")).toHaveValue("");
  await expect(page.getByTestId("dashboard-root")).toHaveCount(0);
  expect(dashboardRequests).toBe(0);
  await page.screenshot({ path: testInfo.outputPath("dashboard-login.png"), fullPage: true });
  // A visibility toggle confirms client hydration before filling controlled fields.
  await page.getByRole("button", { name: "Show password", exact: true }).click();
  await page.getByRole("button", { name: "Hide password", exact: true }).click();
  await page.locator("#login-email").fill(process.env.ADMIN_EMAIL ?? "admin@example.com");
  await page.locator("#login-password").fill(process.env.ADMIN_PASSWORD ?? "ChangeMe123!");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(`${getBaseUrl()}/`, { timeout: 20_000 });
  await expect(page.getByTestId("dashboard-root")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("dashboard-value-today-appointments")).toHaveText("2");
  expect(dashboardRequests).toBeGreaterThan(0);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/login(?:[?#]|$)/);
  const requestsBeforeRevisit = dashboardRequests;
  await page.goto(`${getBaseUrl()}/`, { waitUntil: "domcontentloaded" });
  await expect(page).toHaveURL(/\/login(?:[?#]|$)/);
  await expect(page.getByTestId("dashboard-root")).toHaveCount(0);
  expect(dashboardRequests).toBe(requestsBeforeRevisit);
});

test("desktop navigation is vertical, collapses persistently and still opens Patients and Home", async ({ page, request }) => {
  await primePageAuth(page, request);
  await mockDashboard(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await openDashboard(page);
  const sidebar = page.getByTestId("app-sidebar");
  const navigation = page.getByRole("navigation", { name: "Main navigation" });
  await expect(sidebar).toHaveAttribute("data-collapsed", "false");
  const expanded = await sidebar.boundingBox();
  const main = await page.getByTestId("app-main").boundingBox();
  expect(expanded).not.toBeNull();
  expect(main).not.toBeNull();
  expect(expanded!.width).toBeGreaterThan(150);
  expect(main!.x).toBeGreaterThanOrEqual(expanded!.x + expanded!.width - 1);
  expect(main!.y).toBeLessThan(100);
  const home = await navigation.getByRole("link", { name: "Home", exact: true }).boundingBox();
  const patients = await navigation.getByRole("link", { name: "Patients", exact: true }).boundingBox();
  expect(patients!.y).toBeGreaterThan(home!.y);
  expect(patients!.x).toBeCloseTo(home!.x, 0);
  await page.getByTestId("app-sidebar-toggle").click();
  await expect(sidebar).toHaveAttribute("data-collapsed", "true");
  await expect.poll(async () => (await sidebar.boundingBox())!.width).toBeLessThan(100);
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(sidebar).toHaveAttribute("data-collapsed", "true");
  await navigation.getByRole("link", { name: "Patients", exact: true }).click();
  await expect(page).toHaveURL(/\/patients(?:[?#]|$)/);
  await expect(navigation.getByRole("link", { name: "Patients", exact: true })).toHaveAttribute("aria-current", "page");
  await navigation.getByRole("link", { name: "Home", exact: true }).click();
  await expect(page).toHaveURL(`${getBaseUrl()}/`);
  await expect(page.getByTestId("dashboard-root")).toBeVisible();
  await expectDocumentFits(page);
});

test("mobile navigation opens on demand, dismisses by Escape and backdrop, and closes after a route change", async ({ page, request }) => {
  await primePageAuth(page, request);
  await mockDashboard(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await openDashboard(page);
  const toggle = page.getByTestId("app-mobile-menu-toggle");
  await expect(toggle).toBeVisible();
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  await page.keyboard.press("Escape");
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await toggle.click();
  const backdrop = page.getByTestId("app-sidebar-backdrop");
  const backdropBox = await backdrop.boundingBox();
  expect(backdropBox).not.toBeNull();
  await backdrop.click({ position: { x: backdropBox!.width - 5, y: Math.min(300, backdropBox!.height - 5) } });
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await toggle.click();
  await page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "Patients", exact: true }).click();
  await expect(page).toHaveURL(/\/patients(?:[?#]|$)/);
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await expectDocumentFits(page);
  await toggle.click();
  await page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "Home", exact: true }).click();
  await expect(page.getByTestId("dashboard-root")).toBeVisible();
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await expectDocumentFits(page);
});

test("dashboard renders exact synthetic metrics, identity lists and explicitly unavailable measurements", async ({ page, request }) => {
  await primePageAuth(page, request);
  await mockDashboard(page);
  await openDashboard(page);
  await expect(page.getByTestId("dashboard-value-today-appointments")).toHaveText("2");
  await expect(page.getByTestId("dashboard-value-in-clinic")).toHaveText("1");
  await expect(page.getByTestId("dashboard-value-overdue-payments")).toHaveText("3");
  await expect(page.getByTestId("dashboard-overdue-amount")).toContainText("£127.50");
  await expect(page.getByTestId("dashboard-today-schedule")).toContainText("Synthetic Alex Demo");
  await expect(page.getByTestId("dashboard-today-schedule")).toContainText("Synthetic Jamie Demo");
  await expect(page.getByTestId("dashboard-card-recent-patients")).toContainText("Synthetic Alex Demo");
  await expect(page.getByTestId("dashboard-card-recent-patients")).toContainText("07700 900123");
  await expect(page.getByTestId("dashboard-card-recent-patients")).toContainText(/created|added/i);
  await expect(page.getByTestId("dashboard-overdue-list")).toContainText("DEMO-90001");
  await expect(page.getByTestId("dashboard-card-tomorrow-unconfirmed")).toHaveAttribute("data-state", "unavailable");
  await expect(page.getByTestId("dashboard-card-tomorrow-unconfirmed")).toContainText(/not recorded|unavailable/i);
  await expect(page.getByTestId("dashboard-value-tomorrow-unconfirmed")).toHaveCount(0);
  await expect(page.getByTestId("dashboard-card-recalls")).toContainText(/not recorded|unavailable/i);
  await expect(page.getByTestId("dashboard-week-appointments")).toContainText("8");
  await expect(page.getByTestId("dashboard-week-appointments")).toContainText("-20%");
  await expect(page.getByTestId("dashboard-week-completed")).toContainText("6");
  await expect(page.getByTestId("dashboard-week-completed")).toContainText("75%");
  await expect(page.getByTestId("dashboard-week-completed")).toContainText("+20%");
  await expect(page.getByTestId("dashboard-week-invoiced")).toContainText("£400");
  await expect(page.getByTestId("dashboard-week-invoiced")).toContainText("+33%");
});

test("an overdue invoice dashboard link opens the synthetic patient's Financial tab", async ({ page, request }) => {
  await primePageAuth(page, request);
  const patientId = await createPatient(request, { first_name: "Synthetic", last_name: `Dashboard finance ${Date.now()}` });
  const fixture = dashboardFixture();
  fixture.payments.items[0].patient_id = Number(patientId);
  fixture.payments.items[0].patient_name = "Synthetic dashboard finance";
  await mockDashboard(page, fixture);
  await openDashboard(page);
  const invoiceLink = page.getByTestId("dashboard-overdue-list").getByRole("link").first();
  await expect(invoiceLink).toHaveAttribute("href", `/patients/${patientId}?tab=financial`);
  await invoiceLink.click();
  await expect(page).toHaveURL(new RegExp(`/patients/${patientId}\\?tab=financial`));
  await expect(page.getByTestId("patient-tab-Financial")).toHaveAttribute("aria-selected", "true", { timeout: 20_000 });
  await expect(page.getByTestId("patient-financial-invoices")).toHaveAttribute("aria-selected", "true");
});

test("permission-restricted cards never expose names, amounts or fabricated zeroes", async ({ page, request }) => {
  await primePageAuth(page, request);
  await mockDashboard(page, {
    ...dashboardFixture(),
    appointments: {
      availability: "forbidden", today_count: null, in_clinic_count: null, schedule_availability: "forbidden", schedule: [], schedule_has_more: false,
      unconfirmed_tomorrow: { availability: "forbidden", value: null, reason: "permission_required" }, last_7_days: null, previous_7_days: null,
    },
    payments: { availability: "forbidden", overdue_invoice_count: null, overdue_balance_pence: null, items_availability: "forbidden", items: [], items_has_more: false, last_7_days_invoiced_pence: null, previous_7_days_invoiced_pence: null },
    patients: { availability: "forbidden", recent: [], recent_has_more: false, basis: "created_at" },
    recalls: { availability: "forbidden", due_this_week: null, overdue: null, scheduled_this_month: null, conversion_rate: { availability: "forbidden", value: null, reason: "permission_required" } },
  });
  await page.goto(`${getBaseUrl()}/`, { waitUntil: "domcontentloaded" });
  for (const key of ["today-appointments", "in-clinic", "overdue-payments", "tomorrow-unconfirmed", "recent-patients", "recalls", "week-comparison"]) {
    await expect(page.getByTestId(`dashboard-card-${key}`)).toHaveAttribute("data-state", "forbidden", { timeout: 20_000 });
    await expect(page.getByTestId(`dashboard-value-${key}`)).toHaveCount(0);
  }
  await expect(page.getByTestId("dashboard-root")).not.toContainText("Synthetic Alex Demo");
  await expect(page.getByTestId("dashboard-root")).not.toContainText("07700 900123");
  await expect(page.getByTestId("dashboard-root")).not.toContainText("£0");
  await expect(page.getByTestId("dashboard-overdue-amount")).toHaveCount(0);
});

test("a genuine empty workload displays zero but unrecorded confirmation and conversion stay unavailable", async ({ page, request }) => {
  await primePageAuth(page, request);
  const empty = dashboardFixture();
  empty.appointments.today_count = 0;
  empty.appointments.in_clinic_count = 0;
  empty.appointments.schedule = [];
  empty.payments.overdue_invoice_count = 0;
  empty.payments.overdue_balance_pence = 0;
  empty.payments.items = [];
  empty.patients.recent = [];
  empty.recalls.due_this_week = 0;
  empty.recalls.overdue = 0;
  empty.recalls.scheduled_this_month = 0;
  await mockDashboard(page, empty);
  await openDashboard(page);
  for (const key of ["today-appointments", "in-clinic", "overdue-payments"]) {
    await expect(page.getByTestId(`dashboard-card-${key}`)).toHaveAttribute("data-state", "available");
    await expect(page.getByTestId(`dashboard-value-${key}`)).toHaveText("0");
  }
  await expect(page.getByTestId("dashboard-overdue-amount")).toContainText("£0.00");
  await expect(page.getByTestId("dashboard-card-tomorrow-unconfirmed")).toHaveAttribute("data-state", "unavailable");
  await expect(page.getByTestId("dashboard-value-tomorrow-unconfirmed")).toHaveCount(0);
  await expect(page.getByTestId("dashboard-card-recalls")).toContainText(/not recorded|unavailable/i);
});

test("aggregate access does not reveal patient identity lists without patient-view permission", async ({ page, request }) => {
  await primePageAuth(page, request);
  const restricted = dashboardFixture();
  restricted.appointments.schedule_availability = "forbidden";
  restricted.appointments.schedule = [];
  restricted.payments.items_availability = "forbidden";
  restricted.payments.items = [];
  restricted.patients.availability = "forbidden";
  restricted.patients.recent = [];
  await mockDashboard(page, restricted);
  await openDashboard(page);
  await expect(page.getByTestId("dashboard-value-today-appointments")).toHaveText("2");
  await expect(page.getByTestId("dashboard-value-overdue-payments")).toHaveText("3");
  await expect(page.getByTestId("dashboard-today-schedule")).toContainText(/permission|restricted|access/i);
  await expect(page.getByTestId("dashboard-overdue-list")).toContainText(/permission|restricted|access/i);
  await expect(page.getByTestId("dashboard-card-recent-patients")).toHaveAttribute("data-state", "forbidden");
  await expect(page.getByTestId("dashboard-root")).not.toContainText("Synthetic Alex Demo");
  await expect(page.getByTestId("dashboard-root")).not.toContainText("Synthetic Jamie Demo");
  await expect(page.getByTestId("dashboard-root")).not.toContainText("07700 900123");
});

test("loading and server failure never masquerade as zero workload, and retry loads real metrics", async ({ page, request }) => {
  await primePageAuth(page, request);
  let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  let attempts = 0;
  let allowSuccess = false;
  await page.route(`**${dashboardPath}`, async (route) => {
    attempts += 1;
    // Development StrictMode may mount twice; gate every initial fetch.
    if (!allowSuccess) {
      await gate;
      return route.fulfill({ status: 503, contentType: "text/html", body: "<html>private dashboard infrastructure response</html>" });
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(dashboardFixture()) });
  });
  await page.goto(`${getBaseUrl()}/`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("dashboard-loading")).toBeVisible({ timeout: 20_000 });
  await expect(page.locator('[data-testid^="dashboard-value-"]')).toHaveCount(0);
  release();
  await expect(page.getByTestId("dashboard-error")).toBeVisible({ timeout: 20_000 });
  await expect(page.locator('[data-testid^="dashboard-value-"]')).toHaveCount(0);
  await expect(page.getByTestId("dashboard-root")).not.toContainText("private dashboard infrastructure response");
  const attemptsBeforeRetry = attempts;
  allowSuccess = true;
  await page.getByTestId("dashboard-error").getByRole("button", { name: /retry/i }).click();
  await expect(page.getByTestId("dashboard-value-today-appointments")).toHaveText("2");
  await expect(page.getByTestId("dashboard-error")).toHaveCount(0);
  expect(attempts).toBe(attemptsBeforeRetry + 1);
});

test("dashboard and sidebar remain usable in light and dark themes at desktop and mobile widths", async ({ page, request }, testInfo) => {
  await primePageAuth(page, request);
  await mockSyntheticOperator(page);
  await mockDashboard(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await openDashboard(page);
  await expectDocumentFits(page);
  await page.screenshot({ path: testInfo.outputPath("dashboard-desktop-light.png"), fullPage: true });
  await page.getByRole("button", { name: "Toggle theme", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.screenshot({ path: testInfo.outputPath("dashboard-desktop-dark.png"), fullPage: true });
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.getByTestId("dashboard-value-today-appointments")).toHaveText("2");
  await page.setViewportSize({ width: 390, height: 844 });
  await expectDocumentFits(page);
  await page.screenshot({ path: testInfo.outputPath("dashboard-mobile-dark.png"), fullPage: true });
  await page.getByTestId("app-mobile-menu-toggle").click();
  await expect(page.getByTestId("app-mobile-menu-toggle")).toHaveAttribute("aria-expanded", "true");
  await page.screenshot({ path: testInfo.outputPath("dashboard-mobile-drawer-dark.png") });
});
