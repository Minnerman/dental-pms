import fs from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";

import { expect, test, type Page } from "@playwright/test";

import { getBaseUrl, primePageAuth } from "./helpers/auth";
import { resolvePatientRepresentativeSet } from "./helpers/patient-ui-representatives";

const stage160aDir = path.resolve(__dirname, "..", "..", ".run", "stage160a");
const representativeSetPath = path.join(stage160aDir, "patient_representative_set.json");
const artifactDir = process.env.PATIENT_UI_SCREENSHOT_DIR
  ? path.resolve(process.env.PATIENT_UI_SCREENSHOT_DIR)
  : stage160aDir;
const goldenMode = (process.env.PATIENT_UI_GOLDEN_MODE || "off").toLowerCase();
const goldenHashesPath = process.env.PATIENT_UI_GOLDEN_HASHES
  ? path.resolve(process.env.PATIENT_UI_GOLDEN_HASHES)
  : path.resolve(__dirname, "fixtures", "patient-ui-golden-hashes.json");

async function waitForPatientUiReady(page: Page, patientId: number) {
  await expect(page).toHaveURL(new RegExp(`/patients/${patientId}/clinical`));
  await expect(page.getByRole("link", { name: "← Back to patients" })).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.locator("h2").first()).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText(new RegExp(`Patient #${patientId}\\b`))).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByRole("button", { name: "Summary" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Clinical", exact: true }).first()).toBeVisible();
  await expect(page.getByText("Loading patient…")).toHaveCount(0);
  await expect(page.getByText("Loading clinical…")).toHaveCount(0);
}

async function prepareDeterministicScreenshot(page: Page) {
  await page.locator("body").click({ position: { x: 5, y: 5 } });
  await page.evaluate(() => {
    for (const node of Array.from(document.querySelectorAll("div,span,p"))) {
      const text = (node.textContent || "").trim();
      if (text.startsWith("Last updated:")) {
        node.textContent = "Last updated: —";
      }
    }
  });
  await page.addStyleTag({
    content: `
      *:focus {
        outline: none !important;
        box-shadow: none !important;
      }
      input,
      textarea {
        caret-color: transparent !important;
      }
    `,
  });
}

async function sha256ForFile(filePath: string): Promise<string> {
  const content = await fs.readFile(filePath);
  return createHash("sha256").update(content).digest("hex");
}

test("stage160a patient UI parity screenshot pack", async ({ page, request }) => {
  test.setTimeout(240_000);
  await fs.mkdir(artifactDir, { recursive: true });
  const representative = await resolvePatientRepresentativeSet(request, {
    outputPath: representativeSetPath,
  });
  const baseUrl = getBaseUrl();

  await primePageAuth(page, request);
  const hashes: Record<string, string> = {};
  for (const item of representative.patients) {
    const patientId = item.patient_id;
    await page.goto(`${baseUrl}/patients/${patientId}/clinical`, {
      waitUntil: "domcontentloaded",
    });
    await waitForPatientUiReady(page, patientId);
    await prepareDeterministicScreenshot(page);
    const screenshotName = `patient_ui_${patientId}.png`;
    const screenshotPath = path.join(artifactDir, screenshotName);
    await page.screenshot({
      path: screenshotPath,
      fullPage: true,
    });
    hashes[screenshotName] = await sha256ForFile(screenshotPath);
  }

  const representativePatientIds = representative.patients.map((item) => item.patient_id);
  if (goldenMode === "record") {
    await fs.mkdir(path.dirname(goldenHashesPath), { recursive: true });
    await fs.writeFile(
      goldenHashesPath,
      JSON.stringify(
        {
          representative_patient_ids: representativePatientIds,
          hashes,
        },
        null,
        2
      )
    );
    test.info().annotations.push({
      type: "golden",
      description: `Recorded patient UI golden hashes to ${goldenHashesPath}`,
    });
  } else if (goldenMode === "assert") {
    const raw = await fs.readFile(goldenHashesPath, "utf-8");
    const baseline = JSON.parse(raw) as {
      representative_patient_ids?: number[];
      hashes?: Record<string, string>;
    };
    if (Array.isArray(baseline.representative_patient_ids)) {
      expect(
        representativePatientIds,
        "Representative patient set drifted from baseline."
      ).toEqual(baseline.representative_patient_ids);
    }
    const expected = baseline.hashes || {};
    for (const [name, hash] of Object.entries(hashes)) {
      expect(expected[name], `Missing baseline hash for ${name}`).toBeTruthy();
      expect(hash, `Screenshot drift detected for ${name}`).toBe(expected[name]);
    }
  }
});

test("stage160a patient UI render timing guard", async ({ page, request }) => {
  const representative = await resolvePatientRepresentativeSet(request, {
    outputPath: representativeSetPath,
  });
  const first = representative.patients[0];
  expect(first).toBeTruthy();
  const baseUrl = getBaseUrl();
  const budgetMs = Number(process.env.PATIENT_UI_RENDER_BUDGET_MS ?? "12000");
  const startedAt = Date.now();

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/patients/${first.patient_id}/clinical`, {
    waitUntil: "domcontentloaded",
  });
  await waitForPatientUiReady(page, first.patient_id);

  const elapsedMs = Date.now() - startedAt;
  console.log("PATIENT_UI_RENDER_MS", elapsedMs);
  expect(elapsedMs).toBeLessThan(budgetMs);
});
