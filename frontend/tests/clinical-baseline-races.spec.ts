import { expect, test, type Page } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

function conditionsPath(patientId: string) {
  return `/api/patients/${patientId}/clinical/tooth-conditions`;
}

function gate() {
  let release!: () => void;
  const promise = new Promise<void>((resolve) => { release = resolve; });
  return { promise, release };
}

async function openChart(page: Page, patientId: string) {
  await page.goto(`${getBaseUrl()}/patients/${patientId}/clinical?clinicalView=current`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/loading/i);
  await expect(page.locator(".clinical-refresh-control").getByRole("button", { name: "Refresh", exact: true })).toBeEnabled();
}

async function openMenu(page: Page, tooth: string) {
  await page.getByTestId(`tooth-label-${tooth}`).click({ button: "right" });
  await expect(page.getByTestId("clinical-tooth-action-menu")).toBeVisible();
}

test("a clinical refresh during a pending baseline save cannot overwrite its saved condition", async ({ page, request }) => {
  const token = await primePageAuth(page, request);
  const patientId = await createPatient(request, { first_name: "Synthetic", last_name: `Baseline save race ${Date.now()}` });
  await openChart(page, patientId);

  const started = gate();
  const releaseSave = gate();
  let baselineReadsWhileSaving = 0;
  let pendingSave = false;
  await page.route(`**${conditionsPath(patientId)}`, async (route) => {
    if (route.request().method() === "POST") {
      pendingSave = true;
      started.release();
      await releaseSave.promise;
      await route.continue();
    } else {
      if (pendingSave) baselineReadsWhileSaving += 1;
      await route.continue();
    }
  });

  try {
    await openMenu(page, "UR5");
    const saved = page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === conditionsPath(patientId));
    await page.getByTestId("clinical-baseline-condition-missing").click();
    await started.promise;
    await expect(page.getByTestId("clinical-baseline-status")).toContainText(/saving/i);

    const refreshed = page.waitForResponse((response) => new URL(response.url()).pathname === `/api/patients/${patientId}/clinical/summary`);
    await page.locator(".clinical-refresh-control").getByRole("button", { name: "Refresh", exact: true }).click();
    expect((await refreshed).ok()).toBeTruthy();
    await expect(page.locator(".clinical-refresh-control").getByRole("button", { name: "Refresh", exact: true })).toBeEnabled();
    expect(baselineReadsWhileSaving).toBe(0);

    releaseSave.release();
    expect((await saved).ok()).toBeTruthy();
    pendingSave = false;
    await expect(page.getByTestId("tooth-svg-UR5")).toHaveAttribute("data-baseline-status", "missing");
    await expect(page.getByTestId("clinical-baseline-status")).toContainText(/saved/i);
    await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/loading|saving/i);
    const stored = await request.get(`${getBaseUrl()}${conditionsPath(patientId)}`, { headers: { Authorization: `Bearer ${token}` } });
    expect((await stored.json()).teeth.UR5).toMatchObject({ condition: "missing", revision: 1 });
    await openMenu(page, "UR5");
    await expect(page.getByTestId("clinical-baseline-condition-reset")).toBeEnabled();
  } finally {
    releaseSave.release();
  }
});

test("disabling and reopening the clinical tab discards delayed reads and clears repeat state", async ({ page, request }) => {
  const token = await primePageAuth(page, request);
  const patientId = await createPatient(request, { first_name: "Synthetic", last_name: `Baseline disabled race ${Date.now()}` });
  await openChart(page, patientId);
  await openMenu(page, "UR5");
  const saved = page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === conditionsPath(patientId));
  await page.getByTestId("clinical-baseline-condition-implant").click();
  expect((await saved).ok()).toBeTruthy();
  await expect(page.getByTestId("tooth-svg-UR5")).toHaveAttribute("data-baseline-status", "implant");

  const captured = gate();
  const releaseOldRead = gate();
  const oldReadDelivered = gate();
  let holdNextRead = true;
  await page.route(`**${conditionsPath(patientId)}`, async (route) => {
    if (route.request().method() !== "GET" || !holdNextRead) return route.continue();
    holdNextRead = false;
    const oldSnapshot = await route.fetch();
    captured.release();
    await releaseOldRead.promise;
    await route.fulfill({ response: oldSnapshot });
    oldReadDelivered.release();
  });

  try {
    await page.locator(".clinical-refresh-control").getByRole("button", { name: "Refresh", exact: true }).click();
    await captured.promise;
    await page.getByTestId("patient-tab-Personal").click();
    await expect(page.getByTestId("clinical-chart")).toHaveCount(0);

    const changedElsewhere = await request.post(`${getBaseUrl()}${conditionsPath(patientId)}`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { teeth: ["UR5"], condition: "missing", expected_revisions: { UR5: 1 } },
    });
    expect(changedElsewhere.ok()).toBeTruthy();
    await page.getByTestId("patient-tab-Medical").click();
    await expect(page.getByTestId("tooth-svg-UR5")).toHaveAttribute("data-baseline-status", "missing");

    releaseOldRead.release();
    await oldReadDelivered.promise;
    // Inspect after the browser has had a rendering turn to apply the delayed response.
    await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
    await expect(page.getByTestId("tooth-svg-UR5")).toHaveAttribute("data-baseline-status", "missing");
    await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/loading|saving/i);
    await openMenu(page, "LL6");
    await expect(page.getByTestId("clinical-baseline-repeat")).toBeDisabled();
    await expect(page.getByTestId("clinical-baseline-condition-implant")).toBeEnabled();
  } finally {
    releaseOldRead.release();
  }
});

test("a failed refresh preserves a known missing tooth and blocks edits until a successful refresh", async ({ page, request }) => {
  const token = await primePageAuth(page, request);
  const patientId = await createPatient(request, { first_name: "Synthetic", last_name: `Baseline refresh failure ${Date.now()}` });
  const recorded = await request.post(`${getBaseUrl()}${conditionsPath(patientId)}`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { teeth: ["UR5"], condition: "missing", expected_revisions: { UR5: 0 } },
  });
  expect(recorded.ok()).toBeTruthy();
  await openChart(page, patientId);
  await expect(page.getByTestId("tooth-svg-UR5")).toHaveAttribute("data-baseline-status", "missing");

  await page.route(`**${conditionsPath(patientId)}`, (route) => {
    if (route.request().method() !== "GET") return route.continue();
    return route.fulfill({ status: 500, contentType: "text/plain", body: "Synthetic unavailable response" });
  });
  await page.locator(".clinical-refresh-control").getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(page.getByTestId("clinical-baseline-error")).toContainText(/could not be loaded/i);
  await expect(page.getByTestId("tooth-svg-UR5")).toHaveAttribute("data-baseline-status", "missing");
  await expect(page.getByTestId("tooth-crown-UR5")).toHaveCount(0);
  await openMenu(page, "UR5");
  await expect(page.getByTestId("clinical-baseline-condition-reset")).toBeDisabled();
  await expect(page.getByTestId("clinical-baseline-arch-missing")).toBeDisabled();
  await page.keyboard.press("Escape");

  await page.unroute(`**${conditionsPath(patientId)}`);
  await page.getByTestId("clinical-baseline-error").getByRole("button", { name: "Refresh conditions" }).click();
  await expect(page.getByTestId("clinical-baseline-error")).toHaveCount(0);
  await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/loading/i);
  await expect(page.getByTestId("tooth-svg-UR5")).toHaveAttribute("data-baseline-status", "missing");
  await openMenu(page, "UR5");
  await expect(page.getByTestId("clinical-baseline-condition-reset")).toBeEnabled();
});

test("a pending save remains locked across clinical tab re-entry and reconciles before another edit", async ({ page, request }) => {
  const token = await primePageAuth(page, request);
  const patientId = await createPatient(request, { first_name: "Synthetic", last_name: `Baseline save re-entry ${Date.now()}` });
  await openChart(page, patientId);
  const started = gate();
  const releaseSave = gate();
  const postBodies: Array<{ condition: string; expected_revisions: Record<string, number> }> = [];
  await page.route(`**${conditionsPath(patientId)}`, async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    postBodies.push(route.request().postDataJSON());
    started.release();
    await releaseSave.promise;
    await route.continue();
  });

  try {
    await openMenu(page, "UR5");
    const saved = page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === conditionsPath(patientId));
    await page.getByTestId("clinical-baseline-condition-missing").click();
    await started.promise;
    await page.getByTestId("patient-tab-Personal").click();
    await expect(page.getByTestId("clinical-chart")).toHaveCount(0);
    await page.getByTestId("patient-tab-Medical").click();
    await expect(page.getByTestId("clinical-baseline-status")).toContainText(/saving/i);
    await openMenu(page, "UR5");
    await expect(page.getByTestId("clinical-baseline-condition-reset")).toBeDisabled();
    await expect(page.getByTestId("clinical-baseline-arch-missing")).toBeDisabled();
    await page.keyboard.press("Escape");

    releaseSave.release();
    expect((await saved).ok()).toBeTruthy();
    await expect(page.getByTestId("tooth-svg-UR5")).toHaveAttribute("data-baseline-status", "missing");
    await expect(page.getByTestId("clinical-baseline-status")).toContainText(/saved/i);
    await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/loading|saving/i);
    await openMenu(page, "UR5");
    await expect(page.getByTestId("clinical-baseline-condition-reset")).toBeEnabled();
    const corrected = page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === conditionsPath(patientId));
    await page.getByTestId("clinical-baseline-condition-reset").click();
    expect((await corrected).ok()).toBeTruthy();
    expect(postBodies).toEqual([
      { teeth: ["UR5"], condition: "missing", expected_revisions: { UR5: 0 } },
      { teeth: ["UR5"], condition: "unrecorded", movement: null, rotation: null, expected_revisions: { UR5: 1 } },
    ]);
    await expect(page.getByTestId("tooth-svg-UR5")).toHaveAttribute("data-baseline-status", "unrecorded");
    const stored = await request.get(`${getBaseUrl()}${conditionsPath(patientId)}`, { headers: { Authorization: `Bearer ${token}` } });
    expect((await stored.json()).teeth.UR5).toMatchObject({ condition: "unrecorded", dentition: null, movement: null, rotation: null, revision: 2 });
  } finally {
    releaseSave.release();
  }
});
