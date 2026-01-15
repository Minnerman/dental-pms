import { expect, test } from "@playwright/test";

const adminEmail = process.env.ADMIN_EMAIL ?? "admin@example.com";
const adminPassword = process.env.ADMIN_PASSWORD ?? "ChangeMe123!";

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

test("appointments book=1 deep link opens and then clears on refresh", async ({
  page,
  request,
}) => {
  const baseURL = process.env.FRONTEND_BASE_URL ?? "http://localhost:3100";
  const token = await fetchAccessToken(baseURL, request);
  await page.addInitScript(({ tokenValue }) => {
    localStorage.setItem("dental_pms_token", tokenValue);
    document.cookie = `dental_pms_token=${encodeURIComponent(tokenValue)}; Path=/; SameSite=Lax`;
  }, { tokenValue: token });

  await page.goto("/appointments?date=2026-01-15&book=1", { waitUntil: "networkidle" });
  await expect(page.getByTestId("booking-modal")).toBeVisible();
  await page.waitForURL((url) => !url.searchParams.has("book"));

  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByTestId("booking-modal")).toHaveCount(0);
});
