import { expect, test } from "@playwright/test";

const adminEmail = process.env.ADMIN_EMAIL ?? "admin@example.com";
const adminPassword = process.env.ADMIN_PASSWORD ?? "ChangeMe123!";
const envBase = process.env.FRONTEND_BASE_URL;
const baseURL =
  envBase && !envBase.includes("${")
    ? envBase
    : `http://localhost:${process.env.FRONTEND_PORT ?? "3100"}`;

async function fetchAccessToken(baseURL: string, request: any) {
  const response = await request.post(`${baseURL}/api/auth/login`, {
    data: { email: adminEmail, password: adminPassword },
  });
  expect(response.ok()).toBeTruthy();
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
  await page.getByLabel("Password").fill(adminPassword);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL((url: URL) => !url.pathname.startsWith("/login"), {
    timeout: 15_000,
  });
}

test("appointments book=1 deep link opens and then clears on refresh", async ({
  page,
  request,
}) => {
  const token = await fetchAccessToken(baseURL, request);
  await page.addInitScript(({ tokenValue }) => {
    localStorage.setItem("dental_pms_token", tokenValue);
    document.cookie = `dental_pms_token=${encodeURIComponent(tokenValue)}; Path=/; SameSite=Lax`;
  }, { tokenValue: token });

  await page.goto("/appointments?date=2026-01-15&book=1", { waitUntil: "domcontentloaded" });
  await ensureLoggedIn(page);
  await page.goto("/appointments?date=2026-01-15&book=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("appointments-page")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("booking-modal")).toBeVisible({ timeout: 15_000 });
  await page.waitForURL((url) => !url.searchParams.has("book"), { timeout: 15_000 });

  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("booking-modal")).toHaveCount(0);
});
