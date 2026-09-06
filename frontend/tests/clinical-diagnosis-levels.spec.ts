import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

const levels = ["tooth", "root", "crown", "surface"] as const;
const titles = { tooth: "Tooth level", root: "Root level", crown: "Crown level", surface: "Surface level" };
const palettes = { tooth: "clinical-diagnosis-palette", root: "clinical-root-diagnosis-palette", crown: "clinical-crown-diagnosis-palette", surface: "clinical-surface-diagnosis-palette" };
type Level = typeof levels[number];
type Row = { condition: string | null; dentition: string | null; movement: string | null; rotation: string | null; revision: number };
const conditionsPath = (id: string) => `/api/patients/${id}/clinical/tooth-conditions`;

async function setup(page: Page, request: APIRequestContext, description: string) {
  const token = await primePageAuth(page, request);
  const patientId = await createPatient(request, { first_name: "Synthetic", last_name: `Diagnosis corrections ${description} ${Date.now()}` });
  await page.setViewportSize({ width: 1600, height: 1150 });
  return { patientId, headers: { Authorization: `Bearer ${token}` } };
}

async function snapshot(request: APIRequestContext, id: string, headers: Record<string, string>): Promise<{ teeth: Record<string, Row>; note_teeth: string[] }> {
  const response = await request.get(`${getBaseUrl()}${conditionsPath(id)}`, { headers });
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function ready(page: Page) {
  await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/loading|saving/i, { timeout: 30_000 });
}

async function open(page: Page, id: string) {
  await page.goto(`${getBaseUrl()}/patients/${id}/clinical?clinicalView=current`, { waitUntil: "domcontentloaded" });
  await ready(page);
}

async function chooseLevel(page: Page, level: Level) {
  const tab = page.getByTestId(`diagnosis-level-${level}`);
  await expect(tab).toHaveRole("tab");
  await expect(tab).toHaveAccessibleName(titles[level]);
  await tab.click();
  await expect(tab).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId(palettes[level])).toBeVisible();
  for (const other of levels.filter((value) => value !== level)) {
    await expect(page.getByTestId(`diagnosis-level-${other}`)).toHaveAttribute("aria-selected", "false");
    await expect(page.getByTestId(palettes[other])).toHaveCount(0);
  }
}

async function menuAction(page: Page, id: string, tooth: string, action: string) {
  await page.getByTestId(`tooth-label-${tooth}`).click({ button: "right" });
  const response = page.waitForResponse((value) => value.request().method() === "POST" && new URL(value.url()).pathname === conditionsPath(id));
  await page.getByTestId(`clinical-baseline-condition-${action}`).click();
  const saved = await response;
  expect(saved.ok()).toBeTruthy();
  await ready(page);
  return saved.request().postDataJSON();
}

test("four explicit level tabs open empty palettes without anatomy clicks or implicit saves", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "level tabs");
  await open(page, patientId);
  const mutationPaths: string[] = [];
  page.on("request", (value) => { if (["POST", "PATCH", "PUT", "DELETE"].includes(value.method()) && new URL(value.url()).pathname.startsWith(`/api/patients/${patientId}`)) mutationPaths.push(new URL(value.url()).pathname); });
  await expect(page.getByTestId("clinical-diagnosis-levels")).toHaveRole("tablist");
  await expect(page.getByTestId("clinical-diagnosis-levels")).toHaveAccessibleName("Diagnosis level");
  for (const level of levels) {
    await chooseLevel(page, level);
    await expect(page.getByTestId("clinical-diagnosis-panel")).toBeVisible();
  }
  await expect(page.getByTestId("surface-diagnosis-apply")).toBeDisabled();
  await chooseLevel(page, "root");
  await page.getByTestId("root-diagnosis-palette-filled_sound").click();
  await expect(page.getByTestId("root-diagnosis-apply")).toBeDisabled();
  await page.getByTestId("clinical-root-UR6").click();
  await expect(page.getByTestId("root-diagnosis-apply")).toBeEnabled();
  await chooseLevel(page, "crown");
  await expect(page.locator('[data-root-selected="true"]')).toHaveCount(0);
  await chooseLevel(page, "root");
  await expect(page.getByTestId("root-diagnosis-apply")).toBeDisabled();
  await chooseLevel(page, "tooth");
  await expect(page.getByTestId("diagnosis-palette-present")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Tooth present", exact: true })).toHaveCount(0);
  await page.getByTestId("tooth-label-UR6").click({ button: "right" });
  await expect(page.getByTestId("clinical-baseline-condition-present")).toHaveCount(0);
  await page.keyboard.press("Escape");
  await page.setViewportSize({ width: 390, height: 844 });
  for (const level of levels) {
    await chooseLevel(page, level);
    const box = await page.getByTestId(`diagnosis-level-${level}`).boundingBox();
    expect(box).not.toBeNull();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(390);
  }
  expect(mutationPaths).toEqual([]);
  expect((await snapshot(request, patientId, headers)).teeth).toEqual({});
});

test("deciduous URB survives unerupted condition and reload with upper and lower gum orientation", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "primary unerupted");
  await open(page, patientId);
  expect(await menuAction(page, patientId, "UR2", "deciduous")).toEqual({ teeth: ["UR2"], dentition: "deciduous", expected_revisions: { UR2: 0 } });
  await expect(page.getByTestId("tooth-label-UR2")).toHaveText("URB");
  expect(await menuAction(page, patientId, "UR2", "unerupted")).toEqual({ teeth: ["UR2"], condition: "unerupted", expected_revisions: { UR2: 1 } });
  await menuAction(page, patientId, "LR2", "deciduous");
  await menuAction(page, patientId, "LR2", "unerupted");
  for (const tooth of ["UR2", "LR2"]) {
    await expect(page.getByTestId(`tooth-label-${tooth}`)).toHaveText(`${tooth.slice(0, 2)}B`);
    await expect(page.getByTestId(`tooth-svg-${tooth}`)).toHaveAttribute("data-dentition", "deciduous");
    await expect(page.getByTestId(`tooth-svg-${tooth}`)).toHaveAttribute("data-baseline-status", "unerupted");
    const gum = page.getByTestId(`tooth-baseline-gum-${tooth}`);
    await expect(gum).toHaveAttribute("data-gum-side", tooth[0] === "U" ? "below-crown" : "above-crown");
    const gumBox = await gum.boundingBox();
    const crownBox = await page.getByTestId(`tooth-crown-${tooth}`).boundingBox();
    expect(gumBox).not.toBeNull(); expect(crownBox).not.toBeNull();
    if (tooth[0] === "U") expect(gumBox!.y).toBeGreaterThan(crownBox!.y + crownBox!.height);
    else expect(gumBox!.y + gumBox!.height).toBeLessThan(crownBox!.y);
    await expect(page.getByTestId(`clinical-root-${tooth}`)).toHaveCount(0);
    const stored = (await snapshot(request, patientId, headers)).teeth[tooth];
    expect(stored).toMatchObject({ condition: "unerupted", dentition: "deciduous", revision: 2 });
  }
  await page.reload({ waitUntil: "domcontentloaded" });
  await ready(page);
  for (const tooth of ["UR2", "LR2"]) {
    await expect(page.getByTestId(`tooth-label-${tooth}`)).toHaveText(`${tooth.slice(0, 2)}B`);
    await expect(page.getByTestId(`tooth-svg-${tooth}`)).toHaveAttribute("data-dentition", "deciduous");
    await expect(page.getByTestId(`tooth-svg-${tooth}`)).toHaveAttribute("data-baseline-status", "unerupted");
  }
});

test("missing teeth retain independent movement and rotation markers across reload", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "missing movement");
  await open(page, patientId);
  await menuAction(page, patientId, "UR5", "missing");
  await menuAction(page, patientId, "UR5", "movement_forward");
  await menuAction(page, patientId, "UR5", "rotation_clockwise");
  await menuAction(page, patientId, "LL5", "missing");
  await menuAction(page, patientId, "LL5", "movement_backward");
  for (const [tooth, direction] of [["UR5", "forward"], ["LL5", "backward"]]) {
    await expect(page.getByTestId(`tooth-anatomy-${tooth}`)).toHaveCount(0);
    await expect(page.getByTestId(`tooth-surface-map-${tooth}`)).toHaveCount(0);
    await expect(page.getByTestId(`tooth-movement-${tooth}`)).toHaveAttribute("data-direction", direction);
    await expect(page.getByTestId(`tooth-movement-${tooth}`)).toHaveAttribute("data-marker-size", "large");
    await expect(page.getByTestId(`tooth-position-markers-${tooth}`)).toHaveAttribute("data-marker-side", "missing-slot");
    expect((await snapshot(request, patientId, headers)).teeth[tooth]).toMatchObject({ condition: "missing", movement: direction });
  }
  await expect(page.getByTestId("tooth-rotation-UR5")).toHaveAttribute("data-direction", "clockwise");
  await page.reload({ waitUntil: "domcontentloaded" });
  await ready(page);
  await expect(page.getByTestId("tooth-movement-UR5")).toHaveAttribute("data-direction", "forward");
  await expect(page.getByTestId("tooth-movement-LL5")).toHaveAttribute("data-direction", "backward");
  await expect(page.getByTestId("tooth-rotation-UR5")).toHaveAttribute("data-direction", "clockwise");
  await expect(page.getByTestId("tooth-svg-UR5")).toHaveAttribute("data-baseline-status", "missing");
});

test("saving a tooth note immediately creates a yellow keyboard-accessible sticky note for that tooth", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "clickable notes");
  await open(page, patientId);
  const notes = { UR5: "Synthetic upper tooth note for UR5 only", LL5: "Synthetic lower tooth note for LL5 only" };
  for (const [tooth, note] of Object.entries(notes)) {
    await page.getByTestId(`tooth-label-${tooth}`).click({ button: "right" });
    await page.getByTestId("clinical-chart-menu-add-note").click();
    await page.getByTestId("patient-chart-note-body").fill(note);
    const saved = page.waitForResponse((value) => value.request().method() === "POST" && new URL(value.url()).pathname === `/api/patients/${patientId}/tooth-notes`);
    await page.getByTestId("patient-chart-note-add").click();
    const response = await saved;
    expect(response.ok()).toBeTruthy();
    expect(response.request().postDataJSON()).toEqual({ tooth, surface: null, note });
    const flag = page.getByTestId(`tooth-note-flag-${tooth}`);
    await expect(flag).toBeVisible();
    await expect(flag).toHaveRole("button");
    await expect(flag).toHaveAccessibleName(`Open notes for ${tooth}`);
    await expect(flag.locator('path[fill="#ffe66b"]')).toHaveCount(1);
    await page.getByRole("button", { name: "Close tooth tools", exact: true }).click();
  }
  await page.getByTestId("tooth-note-flag-UR5").click();
  await expect(page.getByTestId("patient-tooth-history")).toContainText(notes.UR5);
  await expect(page.getByTestId("patient-tooth-history")).not.toContainText(notes.LL5);
  await page.getByRole("button", { name: "Close tooth tools", exact: true }).click();
  await page.getByTestId("tooth-note-flag-LL5").focus();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("patient-tooth-history")).toContainText(notes.LL5);
  await expect(page.getByTestId("patient-tooth-history")).not.toContainText(notes.UR5);
  await page.reload({ waitUntil: "domcontentloaded" });
  await ready(page);
  await expect(page.getByTestId("tooth-note-flag-UR5")).toBeVisible();
  await expect(page.getByTestId("tooth-note-flag-LL5")).toBeVisible();
  expect((await snapshot(request, patientId, headers)).note_teeth.sort()).toEqual(["LL5", "UR5"]);
});

test("level tabs respect pending saves and read-only access without retaining cross-mode drafts", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "level safeguards");
  await open(page, patientId);
  await page.getByTestId("diagnosis-palette-missing").click();
  await page.getByTestId("tooth-label-UR5").click();
  let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route(`**${conditionsPath(patientId)}`, async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    await gate;
    await route.fulfill({ status: 500, json: { detail: "Synthetic save failure" } });
  });
  const failed = page.waitForResponse((value) => value.request().method() === "POST" && new URL(value.url()).pathname === conditionsPath(patientId));
  try {
    await page.getByTestId("diagnosis-apply").click();
    await expect(page.getByTestId("clinical-baseline-status")).toContainText(/saving/i);
    for (const level of levels) await expect(page.getByTestId(`diagnosis-level-${level}`)).toBeDisabled();
    await expect(page.getByTestId("diagnosis-level-tooth")).toHaveAttribute("aria-selected", "true");
  } finally { release(); }
  expect((await failed).status()).toBe(500);
  await expect(page.getByTestId("clinical-baseline-error")).toBeVisible();
  expect((await snapshot(request, patientId, headers)).teeth).toEqual({});
  await page.unroute(`**${conditionsPath(patientId)}`);
  await page.getByRole("button", { name: "Refresh conditions", exact: true }).click();
  await ready(page);
  await chooseLevel(page, "surface");
  await page.getByTestId("surface-diagnosis-palette-restored").click();
  await page.getByTestId("clinical-chart-view-history").click();
  await expect(page.getByTestId("clinical-diagnosis-levels")).toHaveCount(0);
  await page.getByTestId("clinical-chart-view-current").click();
  await ready(page);
  await expect(page.getByTestId("diagnosis-level-tooth")).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId("diagnosis-apply")).toBeDisabled();
  await page.route("**/api/me/capabilities", (route) => route.fulfill({ json: ["patients.view", "clinical.view"] }));
  await open(page, patientId);
  for (const level of levels) await chooseLevel(page, level);
  await expect(page.getByTestId("surface-diagnosis-palette-restored")).toBeDisabled();
  await expect(page.getByTestId("surface-diagnosis-apply")).toBeDisabled();
});

test("tooth-specific drafts and delayed history stay attached to their original tooth", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "note target race");
  const upperSaved = "Synthetic saved note belongs only to UR5";
  const lowerSaved = "Synthetic saved note belongs only to LL5";
  const upperDraft = "Synthetic unsaved UR5 draft must not move to LL5";
  for (const [tooth, note] of [["UR5", upperSaved], ["LL5", lowerSaved]]) {
    const response = await request.post(`${getBaseUrl()}/api/patients/${patientId}/tooth-notes`, { headers, data: { tooth, surface: null, note } });
    expect(response.ok()).toBeTruthy();
  }
  await open(page, patientId);
  await page.getByTestId("tooth-note-flag-UR5").click();
  await expect(page.getByTestId("patient-tooth-history")).toContainText(upperSaved);
  await page.getByTestId("patient-chart-note-body").fill(upperDraft);
  await page.getByTestId("tooth-note-flag-LL5").click();
  await expect(page.getByTestId("patient-chart-note-body")).toHaveValue("");
  await expect(page.getByTestId("patient-tooth-history")).toContainText(lowerSaved);

  let captured!: () => void;
  let release!: () => void;
  let delivered!: () => void;
  const capturedPromise = new Promise<void>((resolve) => { captured = resolve; });
  const delayed = new Promise<void>((resolve) => { release = resolve; });
  const deliveredPromise = new Promise<void>((resolve) => { delivered = resolve; });
  let holdNext = true;
  await page.route(`**/api/patients/${patientId}/tooth-history?tooth=UR5`, async (route) => {
    if (!holdNext) return route.continue();
    holdNext = false;
    const old = await route.fetch();
    captured();
    await delayed;
    await route.fulfill({ response: old });
    delivered();
  });
  try {
    await page.getByTestId("tooth-note-flag-UR5").click();
    await capturedPromise;
    await expect(page.getByTestId("patient-chart-note-body")).toHaveValue(upperDraft);
    await page.getByTestId("tooth-note-flag-LL5").click();
    await expect(page.getByTestId("patient-tooth-history")).toContainText(lowerSaved);
    release();
    await deliveredPromise;
    await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
    await expect(page.getByTestId("patient-tooth-history")).toContainText(lowerSaved);
    await expect(page.getByTestId("patient-tooth-history")).not.toContainText(upperSaved);
    await expect(page.getByTestId("patient-chart-note-body")).toHaveValue("");
  } finally { release(); }

  await page.getByTestId("tooth-note-flag-UR5").click();
  await expect(page.getByTestId("patient-chart-note-body")).toHaveValue(upperDraft);
  const saved = page.waitForResponse((value) => value.request().method() === "POST" && new URL(value.url()).pathname === `/api/patients/${patientId}/tooth-notes`);
  await page.getByTestId("patient-chart-note-add").click();
  const response = await saved;
  expect(response.ok()).toBeTruthy();
  expect(response.request().postDataJSON()).toEqual({ tooth: "UR5", surface: null, note: upperDraft });
  await expect(page.getByTestId("patient-chart-note-body")).toHaveValue("");
  await expect(page.getByTestId("patient-tooth-history")).toContainText(upperDraft);
  await page.getByTestId("tooth-note-flag-LL5").click();
  await expect(page.getByTestId("patient-tooth-history")).toContainText(lowerSaved);
  await expect(page.getByTestId("patient-tooth-history")).not.toContainText(upperDraft);
  await expect(page.getByTestId("patient-tooth-history")).not.toContainText(upperSaved);
});
