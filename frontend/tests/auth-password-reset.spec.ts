import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import { ensureAuthReady, getBaseUrl } from "./helpers/auth";

async function createReceptionUser(request: APIRequestContext) {
  const token = await ensureAuthReady(request);
  const baseURL = getBaseUrl();
  const stamp = Date.now();
  const email = `reception.reset.${stamp}@example.com`;
  const temporaryPassword = `TempReset${stamp}!`;

  const response = await request.post(`${baseURL}/api/users`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      email,
      full_name: "Reception Reset Proof",
      role: "receptionist",
      temp_password: temporaryPassword,
    },
  });

  expect(response.ok()).toBeTruthy();
  return { email, temporaryPassword };
}

async function fillLogin(page: Page, email: string, password: string) {
  await page.locator("#login-email").fill(email);
  await page.locator("#login-password").fill(password);
}

async function openAuthPage(page: Page, path: string) {
  await page.goto(`${getBaseUrl()}${path}`, { waitUntil: "networkidle" });
}

test("forgot-password request and reset confirm allow login with the new password", async ({
  page,
  request,
}) => {
  const user = await createReceptionUser(request);
  const newPassword = `FreshReset${Date.now()}!`;

  await openAuthPage(page, "/forgot-password");
  await page.getByLabel("Email").fill(user.email);
  await page.getByRole("button", { name: "Send reset link" }).click();

  await expect(
    page.getByText("If the account exists, a reset link has been generated.")
  ).toBeVisible({ timeout: 15_000 });

  const resetLink = page.getByRole("link", { name: "Open reset form" });
  await expect(resetLink).toBeVisible({ timeout: 15_000 });
  await resetLink.click();

  await expect(page).toHaveURL(/\/reset-password\?token=/);
  await page.waitForLoadState("networkidle");
  await page.getByLabel("New password").fill(newPassword);
  await page.getByLabel("Confirm password").fill(newPassword);
  await page.getByRole("button", { name: "Update password" }).click();

  await expect(
    page.getByText("Password updated. You can now sign in.")
  ).toBeVisible({ timeout: 15_000 });

  await openAuthPage(page, "/login");
  await fillLogin(page, user.email, newPassword);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page).toHaveURL(/\/patients$/, { timeout: 20_000 });
  await expect(page).not.toHaveURL(/\/change-password/, { timeout: 20_000 });
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible({
    timeout: 15_000,
  });
});
