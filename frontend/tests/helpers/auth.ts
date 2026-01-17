import { expect, type APIRequestContext, type Page } from "@playwright/test";

const adminEmail = process.env.ADMIN_EMAIL ?? "admin@example.com";
let cachedAdminToken: string | null = null;

export function getBaseUrl() {
  const envBase = process.env.FRONTEND_BASE_URL;
  if (envBase && !envBase.includes("${")) return envBase;
  return `http://localhost:${process.env.FRONTEND_PORT ?? "3100"}`;
}

export async function ensureAuthReady(request: APIRequestContext) {
  if (cachedAdminToken) return cachedAdminToken;
  const baseURL = getBaseUrl();
  const candidate = process.env.ADMIN_PASSWORD ?? "ChangeMe123!";
  const maxAttempts = 5;

  const loginWithBackoff = async () => {
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      const response = await request.post(`${baseURL}/api/auth/login`, {
        data: { email: adminEmail, password: candidate },
      });
      if (!response.ok()) {
        const body = await response.text();
        console.error("AUTH_LOGIN_FAIL", {
          status: response.status(),
          url: `${baseURL}/api/auth/login`,
          body: body.slice(0, 500),
        });
        if (response.status() === 429) {
          const delayMs = 2000 * Math.pow(2, attempt);
          await new Promise((resolve) => setTimeout(resolve, delayMs));
          continue;
        }
        return null;
      }
      return response.json();
    }
    return null;
  };

  const payload = await loginWithBackoff();
  if (payload) {
    const token = payload.access_token || payload.accessToken;
    const mustChange = Boolean(payload.must_change_password ?? payload.mustChangePassword);
    if (!mustChange) {
      cachedAdminToken = token as string;
      return cachedAdminToken;
    }
    const changeResponse = await request.post(`${baseURL}/api/auth/change-password`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { new_password: candidate },
    });
    if (!changeResponse.ok()) {
      const body = await changeResponse.text();
      console.error("AUTH_CHANGE_PASSWORD_FAIL", {
        status: changeResponse.status(),
        url: `${baseURL}/api/auth/change-password`,
        body: body.slice(0, 500),
      });
    }
    const retryPayload = await loginWithBackoff();
    if (retryPayload) {
      const retryToken = retryPayload.access_token || retryPayload.accessToken;
      cachedAdminToken = retryToken as string;
      return cachedAdminToken;
    }
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
