import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { ensureAuthReady, getBaseUrl } from "./helpers/auth";

type LoginPayload = {
  access_token?: string;
  accessToken?: string;
  must_change_password?: boolean;
  mustChangePassword?: boolean;
};

async function createReadyReceptionSession(request: APIRequestContext) {
  const adminToken = await ensureAuthReady(request);
  const baseUrl = getBaseUrl();
  const stamp = Date.now();
  const email = `reception.shell.${stamp}@example.com`;
  const temporaryPassword = `TempShell${stamp}!`;
  const password = `ReadyShell${stamp}!`;

  const createResponse = await request.post(`${baseUrl}/api/users`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: {
      email,
      full_name: "Reception Shell Proof",
      role: "receptionist",
      temp_password: temporaryPassword,
    },
  });
  expect(createResponse.ok()).toBeTruthy();

  const initialLogin = await request.post(`${baseUrl}/api/auth/login`, {
    data: { email, password: temporaryPassword },
  });
  expect(initialLogin.ok()).toBeTruthy();
  const initialPayload = (await initialLogin.json()) as LoginPayload;
  const initialToken = initialPayload.access_token ?? initialPayload.accessToken;
  expect(initialToken).toBeTruthy();
  expect(
    Boolean(initialPayload.must_change_password ?? initialPayload.mustChangePassword)
  ).toBe(true);

  const changePassword = await request.post(`${baseUrl}/api/auth/change-password`, {
    headers: { Authorization: `Bearer ${initialToken}` },
    data: { new_password: password },
  });
  expect(changePassword.ok()).toBeTruthy();

  const readyLogin = await request.post(`${baseUrl}/api/auth/login`, {
    data: { email, password },
  });
  expect(readyLogin.ok()).toBeTruthy();
  const readyPayload = (await readyLogin.json()) as LoginPayload;
  const token = readyPayload.access_token ?? readyPayload.accessToken;
  expect(token).toBeTruthy();
  expect(Boolean(readyPayload.must_change_password ?? readyPayload.mustChangePassword)).toBe(
    false
  );

  return { email, password, token: token as string };
}

async function primeReceptionSession(page: Page, baseUrl: string, token: string) {
  await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
  await page.evaluate((tokenValue) => {
    localStorage.setItem("dental_pms_token", tokenValue);
    document.cookie = `dental_pms_token=${encodeURIComponent(tokenValue)}; Path=/; SameSite=Lax`;
  }, token);
}

test("reception shell search opens a patient record and sign-out re-locks protected routes", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);
  const baseUrl = getBaseUrl();
  const stamp = Date.now();
  const firstName = `ShellFocus${stamp}`;
  const lastName = "Receiver";
  const partialQuery = firstName.slice(0, 10);
  const fullQuery = `${firstName} ${lastName}`;
  const patientId = await createPatient(request, {
    first_name: firstName,
    last_name: lastName,
  });
  await createPatient(request, {
    first_name: `OtherShell${stamp}`,
    last_name: "Patient",
  });
  const session = await createReadyReceptionSession(request);

  await primeReceptionSession(page, baseUrl, session.token);
  await page.goto(`${baseUrl}/patients`, { waitUntil: "domcontentloaded" });

  const globalSearch = page.getByPlaceholder("Search patients...");
  const signOut = page.getByRole("button", { name: "Sign out" });
  await expect(globalSearch).toBeVisible({ timeout: 20_000 });
  await expect(signOut).toBeVisible({ timeout: 20_000 });

  const partialResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "GET" &&
      url.pathname === "/api/patients/search" &&
      url.searchParams.get("q") === partialQuery
    );
  });
  await globalSearch.fill(partialQuery);
  await partialResponse;

  const targetResult = page
    .locator(".app-top-bar button")
    .filter({ hasText: `${firstName} ${lastName}` })
    .first();
  const distractorResult = page
    .locator(".app-top-bar button")
    .filter({ hasText: `OtherShell${stamp} Patient` });
  await expect(targetResult).toBeVisible({ timeout: 15_000 });
  await expect(distractorResult).toHaveCount(0);

  const fullResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "GET" &&
      url.pathname === "/api/patients" &&
      url.searchParams.get("query") === fullQuery
    );
  });
  await globalSearch.fill(fullQuery);
  await fullResponse;
  await expect(targetResult).toBeVisible({ timeout: 15_000 });
  await targetResult.click();

  await expect(page).toHaveURL(new RegExp(`/patients/${patientId}(?:\\?|$)`), {
    timeout: 20_000,
  });
  await expect(page.getByTestId("patient-header-name")).toContainText(`${firstName} ${lastName}`);
  await expect(globalSearch).toHaveValue("");

  await signOut.click();
  await expect(page).toHaveURL(/\/login(?:\?|$)/, { timeout: 20_000 });
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible({ timeout: 15_000 });

  await page.goto(`${baseUrl}/patients/${patientId}`, { waitUntil: "domcontentloaded" });
  await expect(page).toHaveURL(/\/login(?:\?|$)/, { timeout: 20_000 });
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible({ timeout: 15_000 });
});
