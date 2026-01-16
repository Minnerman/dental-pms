import { expect, test } from "@playwright/test";

const adminEmail = process.env.ADMIN_EMAIL ?? "admin@example.com";
let currentPassword = process.env.ADMIN_PASSWORD ?? "ChangeMe123!";
const fallbackPassword = "ChangeMe123!ChangeMe123!";
const altPassword = "ChangeMe123!ChangeMe123!2";
const envBase = process.env.FRONTEND_BASE_URL;
const baseURL =
  envBase && !envBase.includes("${")
    ? envBase
    : `http://localhost:${process.env.FRONTEND_PORT ?? "3100"}`;

async function fetchAccessToken(baseURL: string, request: any) {
  const response = await request.post(`${baseURL}/api/auth/login`, {
    data: { email: adminEmail, password: currentPassword },
  });
  if (!response.ok()) {
    throw new Error(`Login failed for ${adminEmail} (status ${response.status()})`);
  }
  const payload = await response.json();
  const token = payload.access_token || payload.accessToken;
  expect(token).toBeTruthy();
  return token as string;
}

async function ensureLoggedIn(page: any) {
  if (!page.url().includes("/login")) return;
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible({
    timeout: 10_000,
  });
  await page.getByLabel("Email").fill(adminEmail);
  await page.getByLabel("Password").fill(currentPassword);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL((url: URL) => !url.pathname.startsWith("/login"), {
    timeout: 15_000,
  });
}

async function maybeUpdatePassword(page: any) {
  if (!page.url().includes("/change-password")) return;
  await expect(page.getByRole("heading", { name: "Change password" })).toBeVisible({
    timeout: 10_000,
  });
  const nextPassword =
    currentPassword === fallbackPassword ? altPassword : fallbackPassword;
  await page.getByLabel("New password").fill(nextPassword);
  await page.getByLabel("Confirm password").fill(nextPassword);
  await page.getByRole("button", { name: "Update password" }).click();
  currentPassword = nextPassword;
  await page.waitForURL((url: URL) => !url.pathname.startsWith("/change-password"), {
    timeout: 15_000,
  });
}

async function primeAuthenticatedSession(page: any, request: any) {
  const token = await fetchAccessToken(baseURL, request);
  await page.addInitScript(({ tokenValue }) => {
    localStorage.setItem("dental_pms_token", tokenValue);
    document.cookie = `dental_pms_token=${encodeURIComponent(tokenValue)}; Path=/; SameSite=Lax`;
  }, { tokenValue: token });
}

async function openAppointments(page: any, url: string) {
  await page.goto(url, { waitUntil: "domcontentloaded" });
  await ensureLoggedIn(page);
  await maybeUpdatePassword(page);
  if (!page.url().includes("/appointments")) {
    await page.goto(url, { waitUntil: "domcontentloaded" });
  }
  await page.waitForURL((current: URL) => current.pathname.startsWith("/appointments"), {
    timeout: 15_000,
  });
  await expect(page.getByTestId("appointments-page")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("new-appointment")).toBeVisible({ timeout: 15_000 });
}

test("appointments deep link opens modal and cleans URL", async ({ page, request }) => {
  await primeAuthenticatedSession(page, request);
  await openAppointments(page, "/appointments?date=2026-01-15&book=1");
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 15_000 });
  await page.waitForURL((url) => !url.searchParams.has("book"), { timeout: 15_000 });
});

test("appointments refresh after deep link does not reopen without book param", async ({
  page,
  request,
}) => {
  await primeAuthenticatedSession(page, request);
  await openAppointments(page, "/appointments?date=2026-01-15&book=1");
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 15_000 });
  await page.waitForURL((url) => !url.searchParams.has("book"), { timeout: 15_000 });

  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("booking-modal")).toHaveCount(0);
});

test("appointments navigation back/forward keeps modal state consistent", async ({
  page,
  request,
}) => {
  await primeAuthenticatedSession(page, request);
  await openAppointments(page, "/appointments?date=2026-01-15&book=1");
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 15_000 });
  await page.waitForURL((url) => !url.searchParams.has("book"), { timeout: 15_000 });

  await page.goto("/patients", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Patients" })).toBeVisible({
    timeout: 15_000,
  });
  await page.goBack({ waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("appointments-page")).toBeVisible({ timeout: 15_000 });
  const backUrl = new URL(page.url());
  if (backUrl.searchParams.has("book")) {
    await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 15_000 });
  } else {
    await expect(page.getByTestId("booking-modal")).toHaveCount(0);
  }
});

test("appointments modal survives view and location switches", async ({ page, request }) => {
  await primeAuthenticatedSession(page, request);
  await openAppointments(page, "/appointments?date=2026-01-15");
  await page.getByTestId("new-appointment").click();
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 10_000 });

  await page.getByTestId("appointments-view-calendar").click();
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 10_000 });
  await page.getByTestId("appointments-view-day-sheet").click();
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 10_000 });

  await page.getByLabel("Jump to").fill("2026-01-16");
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 10_000 });

  const clinicianSelect = page.getByLabel("Clinician (optional)");
  const clinicianOptions = await clinicianSelect
    .locator("option")
    .evaluateAll((options) =>
      options
        .map((option) => (option as HTMLOptionElement).value)
        .filter(Boolean)
    );
  if (clinicianOptions.length > 0) {
    await clinicianSelect.selectOption(clinicianOptions[0]);
  }
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 10_000 });

  await page.getByLabel("Location / room").fill("Room 1");
  await page.getByLabel("Location type").selectOption("visit");
  await expect(page.getByLabel("Visit address")).toBeVisible({ timeout: 10_000 });
  await page.getByLabel("Visit address").fill("123 Test Street");
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 10_000 });
});
