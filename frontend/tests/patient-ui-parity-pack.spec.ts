import fs from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";

import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

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
const lockedTabLabels = [
  "Personal",
  "Medical",
  "Schemes",
  "Appointments",
  "Financial",
  "Comms",
  "Notes",
  "Treatment",
];

async function assertLockedTabOrder(page: Page) {
  const tabs = page.getByTestId("patient-tabs").locator("button");
  await expect(tabs).toHaveCount(lockedTabLabels.length);
  await expect(tabs).toHaveText(lockedTabLabels);
  for (const label of lockedTabLabels) {
    await expect(page.getByTestId(`patient-tab-${label}`)).toBeVisible();
  }
}

function buildShortcut(position: number) {
  const modifier = process.platform === "darwin" ? "Meta" : "Control";
  return `${modifier}+${position}`;
}

async function fetchChartingViewerEnabled(
  baseUrl: string,
  request: APIRequestContext
) {
  const response = await request.get(`${baseUrl}/api/config`);
  if (!response.ok()) return null;
  const payload = await response.json();
  const value = payload?.feature_flags?.charting_viewer;
  return typeof value === "boolean" ? value : null;
}

async function waitForPatientUiReady(
  page: Page,
  patientId: number,
  options?: { expectChartingTab?: boolean | null }
) {
  await expect(page).toHaveURL(new RegExp(`/patients/${patientId}/clinical`));
  await expect(page.getByRole("link", { name: "← Back to patients" })).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.locator("h2").first()).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText(new RegExp(`Patient #${patientId}\\b`))).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByTestId("patient-tabs")).toBeVisible();
  await assertLockedTabOrder(page);
  if (options?.expectChartingTab === true) {
    await expect(page.getByTestId("patient-tab-charting")).toBeVisible({ timeout: 20_000 });
  } else if (options?.expectChartingTab === false) {
    await expect(page.getByTestId("patient-tab-charting")).toHaveCount(0);
  }
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
  const chartingEnabled = await fetchChartingViewerEnabled(baseUrl, request);
  const hashes: Record<string, string> = {};
  for (const item of representative.patients) {
    const patientId = item.patient_id;
    await page.goto(`${baseUrl}/patients/${patientId}/clinical`, {
      waitUntil: "domcontentloaded",
    });
    await waitForPatientUiReady(page, patientId, { expectChartingTab: chartingEnabled });
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
  const chartingEnabled = await fetchChartingViewerEnabled(baseUrl, request);
  await page.goto(`${baseUrl}/patients/${first.patient_id}/clinical`, {
    waitUntil: "domcontentloaded",
  });
  await waitForPatientUiReady(page, first.patient_id, { expectChartingTab: chartingEnabled });

  const elapsedMs = Date.now() - startedAt;
  console.log("PATIENT_UI_RENDER_MS", elapsedMs);
  expect(elapsedMs).toBeLessThan(budgetMs);
});

test("stage160b patient tab shortcuts follow locked order", async ({ page, request }) => {
  const representative = await resolvePatientRepresentativeSet(request, {
    outputPath: representativeSetPath,
  });
  const first = representative.patients[0];
  expect(first).toBeTruthy();
  const baseUrl = getBaseUrl();

  await primePageAuth(page, request);
  const chartingEnabled = await fetchChartingViewerEnabled(baseUrl, request);
  await page.goto(`${baseUrl}/patients/${first.patient_id}/clinical`, {
    waitUntil: "domcontentloaded",
  });
  await waitForPatientUiReady(page, first.patient_id, { expectChartingTab: chartingEnabled });
  await page.locator("body").click({ position: { x: 4, y: 4 } });

  for (let index = 0; index < lockedTabLabels.length; index += 1) {
    const label = lockedTabLabels[index];
    await page.locator("body").press(buildShortcut(index + 1));
    const tab = page.getByTestId(`patient-tab-${label}`);
    await expect(tab, `Shortcut failed for ${label}`).toHaveAttribute("aria-selected", "true");
  }
});
