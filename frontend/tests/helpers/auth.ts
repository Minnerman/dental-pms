import { expect, type APIRequestContext, type Page } from "@playwright/test";

const adminEmail = process.env.ADMIN_EMAIL ?? "admin@example.com";
const fallbackPassword = "ChangeMe123!ChangeMe123!";
const altPassword = "ChangeMe123!ChangeMe123!2";
let currentPassword = process.env.ADMIN_PASSWORD ?? "ChangeMe123!";

export function getBaseUrl() {
  const envBase = process.env.FRONTEND_BASE_URL;
  if (envBase && !envBase.includes("${")) return envBase;
  return `http://localhost:${process.env.FRONTEND_PORT ?? "3100"}`;
}

export async function ensureAuthReady(request: APIRequestContext) {
  const baseURL = getBaseUrl();
  const candidates = Array.from(
    new Set([currentPassword, fallbackPassword, altPassword].filter(Boolean))
  );
  for (const candidate of candidates) {
    let response: Awaited<ReturnType<typeof request.post>> | null = null;
    for (let attempt = 0; attempt < 3; attempt += 1) {
      response = await request.post(`${baseURL}/api/auth/login`, {
        data: { email: adminEmail, password: candidate },
      });
      if (response.status() === 429 || response.status() === 503) {
        await new Promise((resolve) => setTimeout(resolve, 500));
        continue;
      }
      break;
    }
    if (!response) continue;
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

export async function primePageAuth(page: Page, request: APIRequestContext) {
  const token = await ensureAuthReady(request);
  await page.addInitScript(
    ({ tokenValue }) => {
      localStorage.setItem("dental_pms_token", tokenValue);
      document.cookie = `dental_pms_token=${encodeURIComponent(tokenValue)}; Path=/; SameSite=Lax`;
    },
    { tokenValue: token }
  );
  return token;
}
