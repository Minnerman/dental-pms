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

async function ensureAuthReady(request: any) {
  const candidates = Array.from(
    new Set([currentPassword, fallbackPassword, altPassword].filter(Boolean))
  );
  for (const candidate of candidates) {
    const response = await request.post(`${baseURL}/api/auth/login`, {
      data: { email: adminEmail, password: candidate },
    });
    if (!response.ok()) continue;
    const payload = await response.json();
    const token = payload.access_token || payload.accessToken;
    const mustChange = Boolean(payload.must_change_password ?? payload.mustChangePassword);
    if (!mustChange) {
      currentPassword = candidate;
      return token as string;
    }
    const nextPassword = candidate === fallbackPassword ? altPassword : fallbackPassword;
    const changeResponse = await request.post(`${baseURL}/api/auth/change-password`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { new_password: nextPassword, old_password: candidate },
    });
    expect(changeResponse.ok()).toBeTruthy();
    currentPassword = nextPassword;
    const retry = await request.post(`${baseURL}/api/auth/login`, {
      data: { email: adminEmail, password: currentPassword },
    });
    expect(retry.ok()).toBeTruthy();
    const retryPayload = await retry.json();
    const retryToken = retryPayload.access_token || retryPayload.accessToken;
    return retryToken as string;
  }
  throw new Error(`Unable to authenticate admin user ${adminEmail}`);
}

async function openAppointments(page: any, request: any, url: string) {
  const token = await ensureAuthReady(request);
  await page.addInitScript(({ tokenValue }) => {
    localStorage.setItem("dental_pms_token", tokenValue);
    document.cookie = `dental_pms_token=${encodeURIComponent(tokenValue)}; Path=/; SameSite=Lax`;
  }, { tokenValue: token });
  await page.goto(url, { waitUntil: "domcontentloaded" });
  await expect(page).toHaveURL(/\/appointments/);
  await expect(page).not.toHaveURL(/\/change-password|\/login/);
  await expect(page.getByTestId("appointments-page")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("new-appointment")).toBeVisible({ timeout: 15_000 });
}

async function clickNewAppointment(page: any) {
  const button = page.getByTestId("new-appointment");
  await expect(button).toBeVisible({ timeout: 15_000 });
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      await button.click();
      return;
    } catch (error) {
      if (attempt === 2) throw error;
      await page.waitForTimeout(250);
    }
  }
}

test("appointments deep link opens modal and cleans URL", async ({ page, request }) => {
  await openAppointments(page, request, "/appointments?date=2026-01-15&book=1");
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 15_000 });
  await page.waitForURL((url) => !url.searchParams.has("book"), { timeout: 15_000 });
});

test("appointments refresh after deep link does not reopen without book param", async ({
  page,
  request,
}) => {
  await openAppointments(page, request, "/appointments?date=2026-01-15&book=1");
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 15_000 });
  await page.waitForURL((url) => !url.searchParams.has("book"), { timeout: 15_000 });

  await page.reload({ waitUntil: "domcontentloaded" });
  await openAppointments(page, request, page.url());
  await expect(page.getByTestId("booking-modal")).toHaveCount(0);
});

test("appointments navigation back/forward keeps modal state consistent", async ({
  page,
  request,
}) => {
  await openAppointments(page, request, "/appointments?date=2026-01-15&book=1");
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 15_000 });
  await page.waitForURL((url) => !url.searchParams.has("book"), { timeout: 15_000 });

  await openAppointments(page, request, "/appointments?date=2026-01-16");
  await page.goBack({ waitUntil: "domcontentloaded" });
  await openAppointments(page, request, page.url());
  const backUrl = new URL(page.url());
  if (backUrl.searchParams.has("book")) {
    await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 15_000 });
  } else {
    await expect(page.getByTestId("booking-modal")).toHaveCount(0);
  }
});

test("appointments modal survives view and location switches", async ({ page, request }) => {
  await openAppointments(page, request, "/appointments?date=2026-01-15");
  await clickNewAppointment(page);
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
