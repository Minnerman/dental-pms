import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import { ensureAuthReady, getBaseUrl } from "./helpers/auth";

type PasswordResetRequestResponse = {
  message?: string;
  reset_token?: string | null;
};

type LoginApiResponse = {
  access_token?: string;
  accessToken?: string;
  must_change_password?: boolean;
  mustChangePassword?: boolean;
};

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
  const emailInput = page.locator("#login-email");
  const passwordInput = page.locator("#login-password");
  const passwordVisibilityToggle = page.getByRole("button", { name: "Show password" });

  // The login form is a controlled client component with seeded defaults. Force one client-side
  // state transition before filling so hydration cannot restore the default email mid-submit.
  await expect(passwordVisibilityToggle).toBeVisible({ timeout: 15_000 });
  await passwordVisibilityToggle.click();
  await expect(
    page.getByRole("button", { name: "Hide password" })
  ).toBeVisible({ timeout: 15_000 });
  await page.getByRole("button", { name: "Hide password" }).click();
  await expect(passwordVisibilityToggle).toBeVisible({ timeout: 15_000 });

  await emailInput.fill(email);
  await expect(emailInput).toHaveValue(email);
  await passwordInput.fill(password);
  await expect(passwordInput).toHaveValue(password);
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
  const resetRequestResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/auth/password-reset/request") &&
      response.request().method() === "POST" &&
      response.status() === 200
  );
  await page.getByLabel("Email").fill(user.email);
  await page.getByRole("button", { name: "Send reset link" }).click();
  const resetRequestResponse = await resetRequestResponsePromise;
  const resetRequestPayload =
    (await resetRequestResponse.json()) as PasswordResetRequestResponse;

  await expect(
    page.getByText("If the account exists, a reset link has been generated.")
  ).toBeVisible({ timeout: 15_000 });

  const resetToken = resetRequestPayload.reset_token ?? null;
  test.skip(
    !resetToken,
    "RESET_TOKEN_DEBUG is disabled in this environment, so the smoke proof cannot open the reset form."
  );
  if (!resetToken) {
    return;
  }

  await openAuthPage(page, `/reset-password?token=${encodeURIComponent(resetToken)}`);
  await expect(page).toHaveURL(/\/reset-password\?token=/);
  await page.getByLabel("New password").fill(newPassword);
  await page.getByLabel("Confirm password").fill(newPassword);
  await page.getByRole("button", { name: "Update password" }).click();

  await expect(
    page.getByText("Password updated. You can now sign in.")
  ).toBeVisible({ timeout: 15_000 });

  await openAuthPage(page, "/login");
  await fillLogin(page, user.email, newPassword);
  const loginResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/auth/login") &&
      response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Sign in" }).click();
  const loginResponse = await loginResponsePromise;
  expect(loginResponse.ok()).toBeTruthy();
  const loginPayload = (await loginResponse.json()) as LoginApiResponse;
  expect(
    Boolean(loginPayload.must_change_password ?? loginPayload.mustChangePassword)
  ).toBe(false);

  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible({
    timeout: 20_000,
  });
  await expect(page).not.toHaveURL(/\/change-password/, { timeout: 20_000 });
  await expect(page).toHaveURL(/\/patients(?:$|[?#])/, { timeout: 20_000 });
});
