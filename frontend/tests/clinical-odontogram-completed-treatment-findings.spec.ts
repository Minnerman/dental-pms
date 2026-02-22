import fs from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

import { getBaseUrl, primePageAuth } from "./helpers/auth";

type ProofPatient = {
  patient_id: number;
  legacy_patient_code?: number;
  min_rows?: number;
};

type ProofPayload =
  | ProofPatient[]
  | {
      patients?: ProofPatient[];
    };

const proofPatientsPath = process.env.COMPLETED_TREATMENT_FINDINGS_PROOF_PATIENTS_FILE
  ? path.resolve(process.env.COMPLETED_TREATMENT_FINDINGS_PROOF_PATIENTS_FILE)
  : path.resolve(
      __dirname,
      "..",
      "..",
      ".run",
      "stage163f",
      "stage163f_completed_treatment_findings_proof_patients.json"
    );

const artifactDir = process.env.COMPLETED_TREATMENT_FINDINGS_ODONTOGRAM_ARTIFACT_DIR
  ? path.resolve(process.env.COMPLETED_TREATMENT_FINDINGS_ODONTOGRAM_ARTIFACT_DIR)
  : path.resolve(__dirname, "..", "..", ".run", "stage163f", "chunk1");

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
      min_rows: Number.isFinite(row.min_rows) ? Number(row.min_rows) : undefined,
    });
  }
  return out;
}

test("clinical page renders for completed treatment findings proof patients", async ({
  page,
  request,
}) => {
  const proofPatients = loadProofPatients(proofPatientsPath);
  test.skip(
    proofPatients.length === 0,
    `No proof patients found. Set COMPLETED_TREATMENT_FINDINGS_PROOF_PATIENTS_FILE or create ${proofPatientsPath}.`
  );

  fs.mkdirSync(artifactDir, { recursive: true });
  await primePageAuth(page, request);

  for (const proof of proofPatients) {
    await page.goto(`${getBaseUrl()}/patients/${proof.patient_id}/clinical`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("Loading clinical…")).toHaveCount(0);

    await page.screenshot({
      path: path.join(
        artifactDir,
        `odontogram_completed_treatment_findings_real_${proof.patient_id}.png`
      ),
      fullPage: true,
    });
  }
});
