import { expect, type APIRequestContext } from "@playwright/test";

import { ensureAuthReady, getBaseUrl } from "./auth";

type PatientOverrides = {
  first_name?: string;
  last_name?: string;
};

type ProcedureOverrides = {
  tooth?: string;
  procedure_code?: string;
  description?: string;
  fee_pence?: number;
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

export async function createClinicalProcedure(
  request: APIRequestContext,
  patientId: string,
  overrides: ProcedureOverrides = {}
) {
  const token = await ensureAuthReady(request);
  const baseURL = getBaseUrl();
  const payload = {
    tooth: overrides.tooth ?? "UR1",
    procedure_code: overrides.procedure_code ?? "PROC",
    description: overrides.description ?? "Test procedure",
    fee_pence: overrides.fee_pence ?? 1200,
  };
  const response = await request.post(`${baseURL}/api/patients/${patientId}/procedures`, {
    headers: { Authorization: `Bearer ${token}` },
    data: payload,
  });
  expect(response.ok()).toBeTruthy();
  const result = await response.json();
  console.log("CREATED_PROCEDURE", result);
  return result;
}
