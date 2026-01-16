import { expect, type APIRequestContext } from "@playwright/test";

import { ensureAuthReady, getBaseUrl } from "./auth";

type PatientOverrides = {
  first_name?: string;
  last_name?: string;
};

export async function createPatient(
  request: APIRequestContext,
  overrides: PatientOverrides = {}
) {
  const token = await ensureAuthReady(request);
  const baseURL = getBaseUrl();
  const unique = Date.now();
  const payload = {
    first_name: overrides.first_name ?? "Test",
    last_name: overrides.last_name ?? `Patient ${unique}`,
  };
  const response = await request.post(`${baseURL}/api/patients`, {
    headers: { Authorization: `Bearer ${token}` },
    data: payload,
  });
  expect(response.ok()).toBeTruthy();
  const data = await response.json();
  return String(data.id);
}
