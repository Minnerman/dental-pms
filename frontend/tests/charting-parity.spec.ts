import fs from "node:fs";
import path from "node:path";

import { test, expect } from "@playwright/test";

import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

type ParityTarget = {
  legacyCode: number;
  patientIdEnv: string;
  entity: "perio-probes" | "bpe" | "notes";
  label: "Perio probes" | "BPE entries" | "Patient notes";
};

const chartingEnabled = process.env.NEXT_PUBLIC_FEATURE_CHARTING_VIEWER === "1";
const parityTargets: ParityTarget[] = [
  {
    legacyCode: 1000000,
    patientIdEnv: "STAGE140_PATIENT_ID_1000000",
    entity: "perio-probes",
    label: "Perio probes",
  },
  {
    legacyCode: 1011978,
    patientIdEnv: "STAGE140_PATIENT_ID_1011978",
    entity: "bpe",
    label: "BPE entries",
  },
  {
    legacyCode: 1012056,
    patientIdEnv: "STAGE140_PATIENT_ID_1012056",
    entity: "notes",
    label: "Patient notes",
  },
];

const hasAllPatientIds = parityTargets.every((target) => process.env[target.patientIdEnv]);
test.skip(!chartingEnabled || !hasAllPatientIds, "charting parity requires env IDs");

function parseBadgeCount(text: string) {
  const match = text.match(/:\s*(\d+)\s*$/);
  if (!match) return null;
  return Number(match[1]);
}

test("charting viewer parity matches API counts", async ({ page, request }) => {
  const token = await ensureAuthReady(request);
  const baseUrl = getBaseUrl();
  const report: Array<{
    legacy_code: number;
    patient_id: string;
    entity: string;
    api_count: number;
    ui_count: number;
    status: "pass" | "fail";
  }> = [];

  await primePageAuth(page, request);

  for (const target of parityTargets) {
    const patientId = process.env[target.patientIdEnv] as string;
    const apiResponse = await request.get(
      `${baseUrl}/api/patients/${patientId}/charting/${target.entity}`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    expect(apiResponse.ok()).toBeTruthy();
    const apiData = (await apiResponse.json()) as unknown[];
    const apiCount = apiData.length;

    await page.goto(`${baseUrl}/patients/${patientId}/charting`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByTestId("charting-viewer")).toBeVisible({ timeout: 30_000 });

    const badge = page.locator(".badge", { hasText: `${target.label}:` }).first();
    await expect(badge).toBeVisible();
    const badgeText = await badge.textContent();
    const uiCount = badgeText ? parseBadgeCount(badgeText) : null;
    expect(uiCount).not.toBeNull();
    expect(uiCount).toBe(apiCount);

    report.push({
      legacy_code: target.legacyCode,
      patient_id: patientId,
      entity: target.label,
      api_count: apiCount,
      ui_count: uiCount as number,
      status: apiCount === uiCount ? "pass" : "fail",
    });
  }

  const reportPath =
    process.env.UI_PARITY_OUT ?? "/tmp/stage140/ui_parity.json";
  fs.mkdirSync(path.dirname(reportPath), { recursive: true });
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  console.log("UI_PARITY_REPORT", JSON.stringify(report));
});
