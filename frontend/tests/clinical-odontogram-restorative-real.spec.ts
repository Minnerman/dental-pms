import fs from "node:fs";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { getBaseUrl, primePageAuth } from "./helpers/auth";

type ProofPatient = {
  patient_id: number;
  legacy_patient_code?: number;
  min_non_crown_glyphs?: number;
};

type ProofPayload =
  | ProofPatient[]
  | {
      patients?: ProofPatient[];
    };

const proofPatientsPath = process.env.RESTORATIVE_PROOF_PATIENTS_FILE
  ? path.resolve(process.env.RESTORATIVE_PROOF_PATIENTS_FILE)
  : path.resolve(__dirname, "..", "..", ".run", "stage163c", "restorative_proof_patients.json");
const artifactDir = process.env.RESTORATIVE_ODONTOGRAM_ARTIFACT_DIR
  ? path.resolve(process.env.RESTORATIVE_ODONTOGRAM_ARTIFACT_DIR)
  : path.resolve(__dirname, "..", "..", ".run", "stage163c");

function loadProofPatients(filePath: string): ProofPatient[] {
  if (!fs.existsSync(filePath)) {
    return [];
  }
  const raw = fs.readFileSync(filePath, "utf-8");
  const payload = JSON.parse(raw) as ProofPayload;
  const rows = Array.isArray(payload) ? payload : Array.isArray(payload.patients) ? payload.patients : [];
  const out: ProofPatient[] = [];
  for (const row of rows) {
    if (!row || !Number.isFinite(row.patient_id)) continue;
    out.push({
      patient_id: Number(row.patient_id),
      legacy_patient_code: Number.isFinite(row.legacy_patient_code)
        ? Number(row.legacy_patient_code)
        : undefined,
      min_non_crown_glyphs: Number.isFinite(row.min_non_crown_glyphs)
        ? Number(row.min_non_crown_glyphs)
        : undefined,
    });
  }
  return out;
}

async function countNonCrownGlyphs(page: Page) {
  const selector = [
    "[data-testid*='-filling']",
    "[data-testid$='-root_canal']",
    "[data-testid$='-post']",
    "[data-testid$='-implant']",
    "[data-testid$='-bridge']",
    "[data-testid$='-denture']",
    "[data-testid$='-extraction']",
    "[data-testid$='-extracted']",
    "[data-testid$='-missing']",
    "[data-testid$='-veneer']",
    "[data-testid$='-inlay_onlay']",
    "[data-testid$='-other']",
  ]
    .map((item) => `[data-testid^='tooth-restoration-']${item}`)
    .join(", ");
  return page.locator(selector).count();
}

test("clinical odontogram renders non-crown restorative glyphs for proof patients", async ({
  page,
  request,
}) => {
  const proofPatients = loadProofPatients(proofPatientsPath);
  test.skip(
    proofPatients.length === 0,
    `No proof patients found. Set RESTORATIVE_PROOF_PATIENTS_FILE or create ${proofPatientsPath}.`
  );

  fs.mkdirSync(artifactDir, { recursive: true });
  await primePageAuth(page, request);

  for (const proof of proofPatients) {
    const minGlyphs = proof.min_non_crown_glyphs ?? 1;
    await page.goto(`${getBaseUrl()}/patients/${proof.patient_id}/clinical`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("Loading clinical…")).toHaveCount(0);

    await expect
      .poll(async () => countNonCrownGlyphs(page), {
        timeout: 30_000,
        message: `Expected >=${minGlyphs} non-crown glyphs for patient ${proof.patient_id}`,
      })
      .toBeGreaterThanOrEqual(minGlyphs);

    await page.screenshot({
      path: path.join(artifactDir, `odontogram_restorative_real_${proof.patient_id}.png`),
      fullPage: true,
    });
  }
});
