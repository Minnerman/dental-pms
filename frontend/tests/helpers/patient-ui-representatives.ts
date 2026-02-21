import fs from "node:fs/promises";
import path from "node:path";

import { type APIRequestContext } from "@playwright/test";

import { ensureAuthReady, getBaseUrl } from "./auth";

type PatientRecord = {
  id: number;
  first_name: string;
  last_name: string;
  date_of_birth?: string | null;
  phone?: string | null;
  email?: string | null;
  address_line1?: string | null;
  notes?: string | null;
  allergies?: string | null;
  medical_alerts?: string | null;
  safeguarding_notes?: string | null;
  alerts_financial?: string | null;
  alerts_access?: string | null;
};

type ClinicalSummaryResponse = {
  recent_tooth_notes?: Array<object>;
  recent_procedures?: Array<object>;
  treatment_plan_items?: Array<object>;
};

type ChartingOverlayResponse = {
  total_items?: number;
};

type PatientRepresentativeRole =
  | "busy_appointments"
  | "charting_dense"
  | "alerts_notes"
  | "minimal"
  | "edge_missing_data";

type PatientRepresentativeMetrics = {
  role: PatientRepresentativeRole;
  patient_id: number;
  display_name: string;
  appointments_count: number;
  chart_items_count: number;
  overlay_items_count: number;
  notes_count: number;
  alerts_count: number;
  missing_dob: boolean;
  missing_core_fields: number;
  reason: string;
};

type PatientRepresentativeSet = {
  generated_at: string;
  selection_method: string;
  scanned_patients: number;
  max_candidates: number;
  patients: PatientRepresentativeMetrics[];
};

type CandidateMetrics = {
  patient: PatientRecord;
  appointments_count: number;
  chart_items_count: number;
  overlay_items_count: number;
  notes_count: number;
  alerts_count: number;
  missing_dob: boolean;
  missing_core_fields: number;
};

type ResolveOptions = {
  outputPath?: string;
  refresh?: boolean;
};

const defaultRepresentativePath = path.resolve(
  __dirname,
  "..",
  "..",
  "..",
  ".run",
  "stage160a",
  "patient_representative_set.json"
);

function nonEmpty(value: unknown) {
  if (value === null || value === undefined) return false;
  return String(value).trim().length > 0;
}

function byDescThenId(a: number, b: number, aId: number, bId: number) {
  if (a !== b) return b - a;
  return aId - bId;
}

function byAscThenId(a: number, b: number, aId: number, bId: number) {
  if (a !== b) return a - b;
  return aId - bId;
}

async function fetchJsonWithToken(
  request: APIRequestContext,
  token: string,
  url: string,
  options?: { tolerateStatus?: number[] }
) {
  const tolerate = new Set(options?.tolerateStatus ?? []);
  const response = await request.get(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (response.ok()) {
    return await response.json();
  }
  if (tolerate.has(response.status())) {
    return null;
  }
  const body = await response.text();
  throw new Error(`Request failed (${response.status()}): ${url} :: ${body.slice(0, 300)}`);
}

async function fetchPatientCandidates(
  request: APIRequestContext,
  token: string,
  maxCandidates: number
): Promise<PatientRecord[]> {
  const baseUrl = getBaseUrl();
  const pageSize = 200;
  const results: PatientRecord[] = [];
  let offset = 0;
  while (results.length < maxCandidates) {
    const payload = (await fetchJsonWithToken(
      request,
      token,
      `${baseUrl}/api/patients?limit=${pageSize}&offset=${offset}`
    )) as PatientRecord[];
    if (!Array.isArray(payload) || payload.length === 0) break;
    results.push(...payload);
    if (payload.length < pageSize) break;
    offset += pageSize;
  }
  return results
    .filter((item) => item && Number.isFinite(item.id))
    .sort((a, b) => a.id - b.id)
    .slice(0, maxCandidates);
}

async function collectCandidateMetrics(
  request: APIRequestContext,
  token: string,
  patient: PatientRecord
): Promise<CandidateMetrics> {
  const baseUrl = getBaseUrl();
  const patientId = patient.id;

  const safeFetch = async (
    url: string,
    options?: { tolerateStatus?: number[] }
  ): Promise<unknown | null> => {
    try {
      return await fetchJsonWithToken(request, token, url, options);
    } catch (error) {
      console.warn("PATIENT_REPRESENTATIVE_METRIC_FAIL", {
        patient_id: patientId,
        url,
        error: error instanceof Error ? error.message : String(error),
      });
      return null;
    }
  };

  const [appointmentsRaw, notesRaw, clinicalRaw, overlayRaw] = await Promise.all([
    safeFetch(`${baseUrl}/api/appointments?patient_id=${patientId}`),
    safeFetch(`${baseUrl}/api/patients/${patientId}/notes`),
    safeFetch(`${baseUrl}/api/patients/${patientId}/clinical/summary?limit=200`, {
      tolerateStatus: [404],
    }),
    safeFetch(
      `${baseUrl}/api/patients/${patientId}/charting/treatment-plan-items?limit=5000&include_planned=true&include_completed=true`,
      { tolerateStatus: [403, 404] }
    ),
  ]);

  const appointmentsCount = Array.isArray(appointmentsRaw) ? appointmentsRaw.length : 0;
  const notesCount = Array.isArray(notesRaw) ? notesRaw.length : 0;
  const clinical = (clinicalRaw || {}) as ClinicalSummaryResponse;
  const chartItemsCount =
    (clinical.recent_tooth_notes?.length ?? 0) +
    (clinical.recent_procedures?.length ?? 0) +
    (clinical.treatment_plan_items?.length ?? 0);
  const overlay = (overlayRaw || {}) as ChartingOverlayResponse;
  const overlayItemsCount = Number.isFinite(overlay.total_items)
    ? Number(overlay.total_items)
    : 0;

  const alertsCount = [
    patient.allergies,
    patient.medical_alerts,
    patient.safeguarding_notes,
    patient.alerts_financial,
    patient.alerts_access,
  ].filter(nonEmpty).length;

  const missingDob = !nonEmpty(patient.date_of_birth);
  const missingCoreFields = [patient.date_of_birth, patient.phone, patient.email, patient.address_line1].filter(
    (value) => !nonEmpty(value)
  ).length;

  return {
    patient,
    appointments_count: appointmentsCount,
    chart_items_count: chartItemsCount,
    overlay_items_count: overlayItemsCount,
    notes_count: notesCount,
    alerts_count: alertsCount,
    missing_dob: missingDob,
    missing_core_fields: missingCoreFields,
  };
}

function asRepresentative(
  role: PatientRepresentativeRole,
  metrics: CandidateMetrics,
  reason: string
): PatientRepresentativeMetrics {
  return {
    role,
    patient_id: metrics.patient.id,
    display_name: `${metrics.patient.first_name} ${metrics.patient.last_name}`.trim(),
    appointments_count: metrics.appointments_count,
    chart_items_count: metrics.chart_items_count,
    overlay_items_count: metrics.overlay_items_count,
    notes_count: metrics.notes_count,
    alerts_count: metrics.alerts_count,
    missing_dob: metrics.missing_dob,
    missing_core_fields: metrics.missing_core_fields,
    reason,
  };
}

function chooseRepresentativeSet(candidates: CandidateMetrics[]): PatientRepresentativeMetrics[] {
  const selected: PatientRepresentativeMetrics[] = [];
  const usedIds = new Set<number>();

  function pick(
    role: PatientRepresentativeRole,
    sortedCandidates: CandidateMetrics[],
    reason: (item: CandidateMetrics) => string
  ) {
    const next = sortedCandidates.find((item) => !usedIds.has(item.patient.id));
    if (!next) return;
    usedIds.add(next.patient.id);
    selected.push(asRepresentative(role, next, reason(next)));
  }

  pick(
    "busy_appointments",
    [...candidates].sort((a, b) =>
      byDescThenId(
        a.appointments_count,
        b.appointments_count,
        a.patient.id,
        b.patient.id
      ) ||
      byDescThenId(
        a.chart_items_count + a.overlay_items_count,
        b.chart_items_count + b.overlay_items_count,
        a.patient.id,
        b.patient.id
      )
    ),
    (item) => `Highest appointments count (${item.appointments_count}).`
  );

  pick(
    "charting_dense",
    [...candidates].sort((a, b) =>
      byDescThenId(
        a.overlay_items_count + a.chart_items_count,
        b.overlay_items_count + b.chart_items_count,
        a.patient.id,
        b.patient.id
      ) ||
      byDescThenId(a.notes_count, b.notes_count, a.patient.id, b.patient.id)
    ),
    (item) =>
      `Highest charting density (${item.overlay_items_count} overlays, ${item.chart_items_count} clinical records).`
  );

  pick(
    "alerts_notes",
    [...candidates].sort((a, b) =>
      byDescThenId(
        a.alerts_count * 1000 + a.notes_count,
        b.alerts_count * 1000 + b.notes_count,
        a.patient.id,
        b.patient.id
      )
    ),
    (item) =>
      item.alerts_count > 0 || item.notes_count > 0
        ? `Alerts/notes rich (${item.alerts_count} alerts, ${item.notes_count} notes).`
        : "Fallback: no alerts/notes-rich patient found in scanned cohort."
  );

  pick(
    "edge_missing_data",
    [...candidates]
      .filter((item) => item.missing_dob || item.missing_core_fields >= 2)
      .sort((a, b) =>
        byDescThenId(
          Number(a.missing_dob) * 100 + a.missing_core_fields,
          Number(b.missing_dob) * 100 + b.missing_core_fields,
          a.patient.id,
          b.patient.id
        )
      ),
    (item) =>
      `Edge case for incomplete data (missing_dob=${item.missing_dob}, missing_core_fields=${item.missing_core_fields}).`
  );

  pick(
    "minimal",
    [...candidates].sort((a, b) =>
      byAscThenId(
        a.appointments_count +
          a.chart_items_count +
          a.overlay_items_count +
          a.notes_count +
          a.alerts_count,
        b.appointments_count +
          b.chart_items_count +
          b.overlay_items_count +
          b.notes_count +
          b.alerts_count,
        a.patient.id,
        b.patient.id
      )
    ),
    (item) =>
      `Lowest activity profile (${item.appointments_count} appointments, ${item.overlay_items_count + item.chart_items_count} charting records).`
  );

  if (selected.length < 5) {
    const fallbacks = [...candidates].sort((a, b) => a.patient.id - b.patient.id);
    for (const item of fallbacks) {
      if (usedIds.has(item.patient.id)) continue;
      usedIds.add(item.patient.id);
      selected.push(asRepresentative("minimal", item, "Fallback selection to complete representative set."));
      if (selected.length >= 5) break;
    }
  }

  return selected.slice(0, 5);
}

export async function resolvePatientRepresentativeSet(
  request: APIRequestContext,
  options: ResolveOptions = {}
): Promise<PatientRepresentativeSet> {
  const outputPath = options.outputPath ?? defaultRepresentativePath;
  const refresh =
    options.refresh ||
    process.env.PATIENT_UI_REPRESENTATIVE_REFRESH === "1" ||
    process.env.PATIENT_UI_REPRESENTATIVE_REFRESH === "true";

  if (!refresh) {
    try {
      const existingRaw = await fs.readFile(outputPath, "utf-8");
      const existing = JSON.parse(existingRaw) as PatientRepresentativeSet;
      if (Array.isArray(existing.patients) && existing.patients.length >= 5) {
        return existing;
      }
    } catch {
      // Build a new deterministic set when file is not present.
    }
  }

  const token = await ensureAuthReady(request);
  const maxCandidates = Number(process.env.PATIENT_UI_REPRESENTATIVE_MAX_PATIENTS ?? "120");
  const patientCandidates = await fetchPatientCandidates(request, token, maxCandidates);
  if (patientCandidates.length === 0) {
    throw new Error("No patients available to build patient UI representative set.");
  }

  const metrics: CandidateMetrics[] = [];
  for (const patient of patientCandidates) {
    metrics.push(await collectCandidateMetrics(request, token, patient));
  }
  const selected = chooseRepresentativeSet(metrics);
  if (selected.length < 5) {
    throw new Error(`Unable to select five representative patients (selected=${selected.length}).`);
  }

  const payload: PatientRepresentativeSet = {
    generated_at: new Date().toISOString(),
    selection_method:
      "Deterministic API-driven ranking over appointments, charting density, alerts/notes, and missing-data edge cases.",
    scanned_patients: metrics.length,
    max_candidates: maxCandidates,
    patients: selected,
  };

  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  await fs.writeFile(outputPath, JSON.stringify(payload, null, 2));
  return payload;
}

export type { PatientRepresentativeSet, PatientRepresentativeMetrics };
