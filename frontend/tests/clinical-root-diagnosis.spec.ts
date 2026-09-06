import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

const rootChoices = [
  { condition: "filled_sound", label: "Filled sound" },
  { condition: "filled_defective", label: "Filled defective" },
  { condition: "post_core_sound", label: "Post & core sound" },
  { condition: "post_core_defective", label: "Post & core defective" },
] as const;
type RootCondition = typeof rootChoices[number]["condition"];
type RootObservation = { condition: RootCondition | null; apicectomy: boolean };
type RootMutation = Partial<RootObservation> & { teeth: string[]; expected_revisions: Record<string, number> };
type RootAction = RootCondition | "apicectomy" | "reset";
type Snapshot = {
  patient_id: number;
  teeth: Record<string, { condition: string | null; revision: number; root_observations: Record<string, RootObservation> }>;
  note_teeth: string[];
};

function toothPath(patientId: string) { return `/api/patients/${patientId}/clinical/tooth-conditions`; }
function rootPath(patientId: string) { return `/api/patients/${patientId}/clinical/root-conditions`; }

async function setup(page: Page, request: APIRequestContext, title: string) {
  const token = await primePageAuth(page, request);
  const patientId = await createPatient(request, { first_name: "Synthetic", last_name: `${title} ${Date.now()}` });
  await page.setViewportSize({ width: 1440, height: 1000 });
  return { patientId, headers: { Authorization: `Bearer ${token}` } };
}

async function readJson(request: APIRequestContext, path: string, headers: Record<string, string>) {
  const response = await request.get(`${getBaseUrl()}${path}`, { headers });
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function snapshot(request: APIRequestContext, patientId: string, headers: Record<string, string>): Promise<Snapshot> {
  return readJson(request, toothPath(patientId), headers);
}

async function recordRoots(request: APIRequestContext, patientId: string, headers: Record<string, string>, data: RootMutation) {
  const response = await request.post(`${getBaseUrl()}${rootPath(patientId)}`, { headers, data });
  expect(response.ok()).toBeTruthy();
  return response.json() as Promise<Snapshot>;
}

async function ready(page: Page) {
  await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/loading|saving/i);
}

async function openChart(page: Page, patientId: string) {
  await page.goto(`${getBaseUrl()}/patients/${patientId}/clinical?clinicalView=current`, { waitUntil: "domcontentloaded" });
  await ready(page);
  await expect(page.getByTestId("clinical-diagnosis-palette")).toBeVisible();
}

async function activateRoots(page: Page, tooth: string) {
  await page.getByTestId(`clinical-root-${tooth}`).click();
  await expect(page.getByTestId("clinical-root-diagnosis-palette")).toBeVisible();
  await expect(page.getByTestId("clinical-diagnosis-palette")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Close tooth tools", exact: true })).toHaveCount(0);
  await expect(page.getByTestId("patient-tooth-history")).toHaveCount(0);
}

async function selectRoots(page: Page, action: RootAction, teeth: string[]) {
  await activateRoots(page, teeth[0]);
  await page.getByTestId(`root-diagnosis-palette-${action}`).click();
  await expect(page.getByTestId(`root-diagnosis-palette-${action}`)).toHaveAttribute("aria-pressed", "true");
  for (const tooth of teeth.slice(1)) await page.getByTestId(`clinical-root-${tooth}`).click();
  for (const tooth of teeth) await expect(page.getByTestId(`clinical-root-${tooth}`)).toHaveAttribute("data-root-selected", "true");
}

async function openRootMenu(page: Page, tooth: string) {
  await page.getByTestId(`clinical-root-${tooth}`).click({ button: "right" });
  const menu = page.getByTestId("clinical-root-action-menu");
  await expect(menu).toBeVisible();
  await expect(menu).toHaveAccessibleName(`Root area actions for ${tooth}`);
  return menu;
}

function nextSave(page: Page, path: string) {
  return page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === path);
}

async function applyRoots(page: Page, patientId: string) {
  const saved = nextSave(page, rootPath(patientId));
  await page.getByTestId("root-diagnosis-apply").click();
  const response = await saved;
  expect(response.ok()).toBeTruthy();
  await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/saving/i);
  return response.request().postDataJSON() as RootMutation;
}

async function rootMenuAction(page: Page, patientId: string, tooth: string, controlId: string) {
  await openRootMenu(page, tooth);
  const saved = nextSave(page, rootPath(patientId));
  await page.getByTestId(controlId).click();
  const response = await saved;
  expect(response.ok()).toBeTruthy();
  await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/saving/i);
  return response.request().postDataJSON() as RootMutation;
}

async function rootDrawing(page: Page, tooth: string, count: number, condition: RootCondition | null, apicectomy: boolean, recorded: boolean) {
  await expect(page.locator(`[data-testid^="clinical-root-drawing-${tooth}-"]`)).toHaveCount(count);
  for (let root = 1; root <= count; root += 1) {
    const target = page.getByTestId(`clinical-root-drawing-${tooth}-${root}`);
    await expect(target).toHaveAttribute("data-root-condition", condition ?? "unspecified");
    await expect(target).toHaveAttribute("data-root-recorded", String(recorded));
    await expect(target).toHaveAttribute("data-apicectomy", String(apicectomy));
    await expect(page.getByTestId(`clinical-root-finding-${tooth}-${root}`)).toHaveCount(condition ? 1 : 0);
    await expect(page.getByTestId(`clinical-root-defect-${tooth}-${root}`)).toHaveCount(condition?.endsWith("defective") ? 1 : 0);
    await expect(page.getByTestId(`clinical-root-apicectomy-${tooth}-${root}`)).toHaveCount(apicectomy ? 1 : 0);
  }
}

function expectedRoots(count: number, condition: RootCondition | null, apicectomy: boolean) {
  return Object.fromEntries(Array.from({ length: count }, (_, index) => [String(index + 1), { condition, apicectomy }]));
}

function observeWrites(page: Page, patientId: string) {
  const roots: RootMutation[] = [];
  const teeth: unknown[] = [];
  const other: string[] = [];
  page.on("request", (outgoing) => {
    if (!["POST", "PUT", "PATCH", "DELETE"].includes(outgoing.method())) return;
    const path = new URL(outgoing.url()).pathname;
    if (path === rootPath(patientId)) roots.push(outgoing.postDataJSON() as RootMutation);
    else if (path === toothPath(patientId)) teeth.push(outgoing.postDataJSON());
    else if (/\/api\/(?:patients|invoices|payments|treatment)/.test(path)) other.push(path);
  });
  return { roots, teeth, other };
}

test("one whole-root area switches palettes while its right-click menu remains diagnosis-only", async ({ page, request }) => {
  const { patientId } = await setup(page, request, "Root area palette switching");
  await openChart(page, patientId);
  const writes = observeWrites(page, patientId);
  await expect(page.getByRole("button", { name: "UR6 root area", exact: true })).toHaveCount(1);
  await expect(page.getByTestId("clinical-root-UR6-1")).toHaveCount(0);
  await expect(page.getByTestId("clinical-root-hit-UR6")).toBeAttached();
  await activateRoots(page, "UR6");
  await expect(page.getByTestId("clinical-root-action-menu")).toHaveCount(0);
  await expect(page.getByTestId("root-diagnosis-selection")).toContainText("UR6");
  await expect(page.getByTestId("root-diagnosis-apply")).toBeDisabled();
  await expect(page.getByTestId("clinical-root-diagnosis-palette").locator('[data-testid^="root-diagnosis-palette-"]')).toHaveCount(6);
  await page.getByTestId("root-diagnosis-palette-filled_sound").click();
  await expect(page.getByTestId("clinical-root-UR6")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("root-diagnosis-apply")).toBeEnabled();
  expect(writes.roots).toEqual([]);
  await page.getByTestId("tooth-label-UR5").click();
  await expect(page.getByTestId("clinical-diagnosis-palette")).toBeVisible();
  await expect(page.getByTestId("clinical-root-diagnosis-palette")).toHaveCount(0);
  await expect(page.locator('[data-root-selected="true"]')).toHaveCount(0);

  const menu = await openRootMenu(page, "UR6");
  await expect(menu.getByRole("menuitemradio")).toHaveCount(4);
  for (const choice of rootChoices) {
    await expect(menu.getByRole("menuitemradio", { name: choice.label, exact: true })).toBeVisible();
    await expect(menu.getByTestId(`clinical-root-condition-${choice.condition}`)).toHaveCSS("font-size", "18px");
  }
  await expect(menu).not.toContainText(/Root [123]/);
  await expect(page.getByTestId("clinical-tooth-action-menu")).toHaveCount(0);
  await expect(page.getByTestId("clinical-chart-menu-add-procedure")).toHaveCount(0);
  await expect(page.getByTestId("clinical-chart-menu-add-plan")).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("clinical-root-UR6")).toBeFocused();
  await page.keyboard.press("Shift+F10");
  await expect(menu).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByTestId("tooth-label-UR6").click({ button: "right" });
  await expect(page.getByTestId("clinical-tooth-action-menu")).toBeVisible();
  await expect(page.getByTestId("clinical-root-condition-filled_sound")).toHaveCount(0);
  expect(writes.roots).toEqual([]);
  expect(writes.teeth).toEqual([]);
  expect(writes.other).toEqual([]);
});

test("an explicit multi-tooth Apply sets every natural root and survives reload without billing", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "Root area batch conditions");
  const originalFinance = await readJson(request, `/api/patients/${patientId}/finance-summary`, headers);
  await openChart(page, patientId);
  const writes = observeWrites(page, patientId);
  const before = await page.getByTestId("tooth-svg-UR6").boundingBox();
  let revision = 0;
  for (const choice of rootChoices) {
    await selectRoots(page, choice.condition, ["UR6", "LR6"]);
    if (revision === 0) {
      await page.getByTestId("clinical-root-UR5").click();
      await page.getByTestId("clinical-root-UR5").click();
      await expect(page.getByTestId("clinical-root-UR5")).toHaveAttribute("data-root-selected", "false");
      await page.getByTestId("root-diagnosis-palette-post_core_sound").click();
      await page.getByTestId("root-diagnosis-palette-filled_sound").click();
      expect((await snapshot(request, patientId, headers)).teeth).toEqual({});
      expect(writes.roots).toEqual([]);
    }
    expect(await applyRoots(page, patientId)).toEqual({ teeth: ["UR6", "LR6"], condition: choice.condition, expected_revisions: { UR6: revision, LR6: revision } });
    revision += 1;
    const stored = await snapshot(request, patientId, headers);
    expect(Object.keys(stored.teeth).sort()).toEqual(["LR6", "UR6"]);
    expect(stored.teeth.UR6).toMatchObject({ condition: null, revision, root_observations: expectedRoots(3, choice.condition, false) });
    expect(stored.teeth.LR6).toMatchObject({ condition: null, revision, root_observations: expectedRoots(2, choice.condition, false) });
    await rootDrawing(page, "UR6", 3, choice.condition, false, true);
    await rootDrawing(page, "LR6", 2, choice.condition, false, true);
    await rootDrawing(page, "UR5", 1, null, false, false);
    const after = await page.getByTestId("tooth-svg-UR6").boundingBox();
    expect(after!.width).toBeCloseTo(before!.width, 1);
    expect(after!.height).toBeCloseTo(before!.height, 1);
    await expect(page.locator('[data-root-selected="true"]')).toHaveCount(0);
    await expect(page.getByTestId("root-diagnosis-apply")).toBeDisabled();
  }
  await page.reload({ waitUntil: "domcontentloaded" });
  await ready(page);
  await rootDrawing(page, "UR6", 3, "post_core_defective", false, true);
  await rootDrawing(page, "LR6", 2, "post_core_defective", false, true);
  await expect(page.getByTestId("clinical-diagnosis-palette")).toBeVisible();
  expect(writes.roots).toHaveLength(4);
  expect(writes.teeth).toEqual([]);
  expect(writes.other).toEqual([]);
  expect(await readJson(request, `/api/patients/${patientId}/finance-summary`, headers)).toEqual(originalFinance);
  expect(await readJson(request, `/api/patients/${patientId}/clinical/summary`, headers)).toMatchObject({ recent_procedures: [], treatment_plan_items: [], recent_tooth_notes: [] });
});

test("root-area apicectomy and resets affect all roots but retain notes and other teeth", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "Root area reset retention");
  const primary = await request.post(`${getBaseUrl()}${toothPath(patientId)}`, { headers, data: { teeth: ["UR5", "LR5"], condition: "deciduous", expected_revisions: { UR5: 0, LR5: 0 } } });
  expect(primary.ok()).toBeTruthy();
  await recordRoots(request, patientId, headers, { teeth: ["UR5", "LR5"], condition: "filled_defective", apicectomy: true, expected_revisions: { UR5: 1, LR5: 1 } });
  const note = await request.post(`${getBaseUrl()}/api/patients/${patientId}/tooth-notes`, { headers, data: { tooth: "UR5", surface: null, note: "Synthetic root area note retained after reset" } });
  expect(note.ok()).toBeTruthy();
  const historyBefore = await readJson(request, `/api/patients/${patientId}/tooth-history?tooth=UR5`, headers);
  await openChart(page, patientId);
  await expect(page.getByTestId("tooth-label-UR5")).toHaveText("URE");
  await rootDrawing(page, "UR5", 3, "filled_defective", true, true);
  await rootDrawing(page, "LR5", 2, "filled_defective", true, true);
  expect(await rootMenuAction(page, patientId, "UR5", "clinical-root-apicectomy")).toEqual({ teeth: ["UR5"], apicectomy: false, expected_revisions: { UR5: 2 } });
  await rootDrawing(page, "UR5", 3, "filled_defective", false, true);
  await rootDrawing(page, "LR5", 2, "filled_defective", true, true);
  await selectRoots(page, "apicectomy", ["UR5", "LR5"]);
  expect(await applyRoots(page, patientId)).toEqual({ teeth: ["UR5", "LR5"], apicectomy: true, expected_revisions: { UR5: 3, LR5: 2 } });
  await rootDrawing(page, "UR5", 3, "filled_defective", true, true);
  expect(await rootMenuAction(page, patientId, "UR5", "clinical-root-reset")).toEqual({ teeth: ["UR5"], condition: null, apicectomy: false, expected_revisions: { UR5: 4 } });
  await rootDrawing(page, "UR5", 3, null, false, true);
  await rootDrawing(page, "LR5", 2, "filled_defective", true, true);
  await selectRoots(page, "reset", ["UR5", "LR5"]);
  expect(await applyRoots(page, patientId)).toEqual({ teeth: ["UR5", "LR5"], condition: null, apicectomy: false, expected_revisions: { UR5: 5, LR5: 2 } });
  await page.reload({ waitUntil: "domcontentloaded" });
  await ready(page);
  await rootDrawing(page, "UR5", 3, null, false, true);
  await rootDrawing(page, "LR5", 2, null, false, true);
  await expect(page.getByTestId("tooth-label-UR5")).toHaveText("URE");
  await page.getByTestId("tooth-label-UR5").click({ button: "right" });
  const reset = nextSave(page, toothPath(patientId));
  await page.getByTestId("clinical-baseline-condition-reset").click();
  expect((await reset).ok()).toBeTruthy();
  await expect(page.getByTestId("tooth-label-UR5")).toHaveText("UR5");
  await rootDrawing(page, "UR5", 1, null, false, false);
  expect((await snapshot(request, patientId, headers)).teeth.UR5).toMatchObject({ condition: "unrecorded", root_observations: {} });
  await expect(page.getByTestId("tooth-note-flag-UR5")).toBeVisible();
  expect(await readJson(request, `/api/patients/${patientId}/tooth-history?tooth=UR5`, headers)).toEqual(historyBefore);
});

test("native root-area findings suppress conflicting historical absence only in Current", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "Root area history precedence");
  await recordRoots(request, patientId, headers, { teeth: ["UR6"], condition: "filled_sound", expected_revisions: { UR6: 0 } });
  const historical = { patient_id: Number(patientId), legacy_patient_code: null, teeth: { "16": { missing: true, extracted: true, restorations: [
    { type: "implant", surfaces: [], meta: { source: "synthetic-test", code_label: "Synthetic historical implant" } },
    { type: "extraction", surfaces: [], meta: { source: "synthetic-test", code_label: "Synthetic historical extraction" } },
  ] } } };
  await page.route(`**/api/patients/${patientId}/charting/tooth-state*`, (route) => route.fulfill({ json: historical }));
  await openChart(page, patientId);
  const writes = observeWrites(page, patientId);
  await rootDrawing(page, "UR6", 3, "filled_sound", false, true);
  await page.getByTestId("clinical-chart-view-history").click();
  for (const mark of ["missing", "extracted", "implant", "extraction"]) await expect(page.getByTestId(`tooth-restoration-UR6-${mark}`)).toBeAttached();
  await expect(page.getByTestId("tooth-badge-UR6").locator('[title="Missing tooth"]')).toHaveText("M");
  await expect(page.getByTestId("tooth-badge-UR6").locator('[title="Extracted tooth"]')).toHaveText("X");
  await expect(page.getByTestId("clinical-root-finding-UR6-1")).toHaveCount(0);
  await page.getByTestId("clinical-chart-view-current").click();
  await rootDrawing(page, "UR6", 3, "filled_sound", false, true);
  for (const mark of ["missing", "extracted", "implant", "extraction"]) await expect(page.getByTestId(`tooth-restoration-UR6-${mark}`)).toHaveCount(0);
  await expect(page.getByTestId("tooth-badge-UR6").locator('[title="Missing tooth"], [title="Extracted tooth"]')).toHaveCount(0);
  await expect(page.getByTestId("tooth-svg-UR6")).not.toHaveAttribute("data-baseline-status", "present");
  expect((await snapshot(request, patientId, headers)).teeth.UR6.condition).toBeNull();
  expect(writes.roots).toEqual([]);
  expect(writes.teeth).toEqual([]);
});

test("Cancel back tooth-number and view changes clear pending roots while viewers cannot edit", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "Root area boundaries");
  await openChart(page, patientId);
  const writes = observeWrites(page, patientId);
  await selectRoots(page, "filled_sound", ["UR6", "LR6"]);
  await page.getByTestId("root-diagnosis-cancel").click();
  await expect(page.getByTestId("clinical-root-diagnosis-palette")).toBeVisible();
  await expect(page.locator('[data-root-selected="true"]')).toHaveCount(0);
  await expect(page.getByTestId("root-diagnosis-apply")).toBeDisabled();
  await selectRoots(page, "post_core_sound", ["UR6"]);
  await page.getByTestId("root-diagnosis-back").click();
  await expect(page.getByTestId("clinical-diagnosis-palette")).toBeVisible();
  await expect(page.locator('[data-root-selected="true"]')).toHaveCount(0);
  await selectRoots(page, "filled_sound", ["UR6"]);
  await page.getByTestId("tooth-label-LL6").click();
  await expect(page.getByTestId("clinical-diagnosis-palette")).toBeVisible();
  await expect(page.locator('[data-root-selected="true"]')).toHaveCount(0);
  for (const tooth of ["UR6", "LR6"]) {
    await selectRoots(page, "filled_sound", ["UR6", "LR6"]);
    await page.getByTestId(`tooth-surface-${tooth}-M`).click({ button: "right" });
    await expect(page.getByTestId("clinical-surface-diagnosis-palette")).toBeVisible();
    await expect(page.getByTestId("clinical-diagnosis-palette")).toHaveCount(0);
    await expect(page.getByTestId("clinical-surface-apply")).toBeDisabled();
    await expect(page.getByTestId("clinical-root-diagnosis-palette")).toHaveCount(0);
    await expect(page.locator('[data-root-selected="true"]')).toHaveCount(0);
    await expect(page.getByTestId("clinical-root-action-menu")).toHaveCount(0);
    await page.keyboard.press("Escape");
  }
  for (const mode of ["planned", "history"]) {
    await selectRoots(page, "filled_sound", ["UR6"]);
    await page.getByTestId(`clinical-chart-view-${mode}`).click();
    await expect(page.getByTestId("clinical-root-diagnosis-palette")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "UR6 root area", exact: true })).toHaveCount(0);
    await page.getByTestId("clinical-chart-view-current").click();
    await ready(page);
    await expect(page.getByTestId("clinical-diagnosis-palette")).toBeVisible();
  }
  await selectRoots(page, "filled_sound", ["UR6"]);
  await page.getByTestId("patient-tab-Personal").click();
  await expect(page.getByTestId("clinical-root-diagnosis-palette")).toHaveCount(0);
  await openChart(page, patientId);
  expect((await snapshot(request, patientId, headers)).teeth).toEqual({});
  await selectRoots(page, "filled_sound", ["UR6"]);
  const nextPatientId = await createPatient(request, { first_name: "Synthetic", last_name: `Root area next patient ${Date.now()}` });
  await openChart(page, nextPatientId);
  await expect(page.getByTestId("clinical-root-diagnosis-palette")).toHaveCount(0);
  await expect(page.locator('[data-root-selected="true"]')).toHaveCount(0);
  expect((await snapshot(request, nextPatientId, headers)).teeth).toEqual({});
  await page.route("**/api/me/capabilities", (route) => route.fulfill({ json: ["patients.view", "clinical.view"] }));
  await openChart(page, patientId);
  await expect(page.getByTestId("patient-clinical-section")).toHaveAttribute("data-clinical-mode", "read-only");
  await activateRoots(page, "UR6");
  for (const action of [...rootChoices.map((choice) => choice.condition), "apicectomy", "reset"]) await expect(page.getByTestId(`root-diagnosis-palette-${action}`)).toBeDisabled();
  await expect(page.getByTestId("root-diagnosis-apply")).toBeDisabled();
  const menu = await openRootMenu(page, "UR6");
  for (const choice of rootChoices) await expect(menu.getByRole("menuitemradio", { name: choice.label, exact: true })).toBeDisabled();
  await expect(menu.getByTestId("clinical-root-apicectomy")).toBeDisabled();
  await expect(menu.getByTestId("clinical-root-reset")).toBeDisabled();
  expect(writes.roots).toEqual([]);
  expect(writes.teeth).toEqual([]);
});

test("root batches reject a stale tooth atomically and protect concurrent roots from whole-tooth reset", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "Root area atomic conflict");
  await openChart(page, patientId);
  await selectRoots(page, "filled_sound", ["UR6", "LR6"]);
  const reset = await request.post(`${getBaseUrl()}${toothPath(patientId)}`, { headers, data: { teeth: ["UR6"], condition: "unrecorded", movement: null, rotation: null, expected_revisions: { UR6: 0 } } });
  expect(reset.ok()).toBeTruthy();
  const conflict = nextSave(page, rootPath(patientId));
  await page.getByTestId("root-diagnosis-apply").click();
  const response = await conflict;
  expect(response.status()).toBe(409);
  expect(response.request().postDataJSON()).toEqual({ teeth: ["UR6", "LR6"], condition: "filled_sound", expected_revisions: { UR6: 0, LR6: 0 } });
  await expect(page.getByTestId("clinical-baseline-error")).toContainText(/changed.*Refresh/i);
  const failed = await snapshot(request, patientId, headers);
  expect(Object.keys(failed.teeth)).toEqual(["UR6"]);
  expect(failed.teeth.UR6).toMatchObject({ condition: "unrecorded", revision: 1, root_observations: {} });
  await rootDrawing(page, "LR6", 2, null, false, false);
  await page.getByRole("button", { name: "Refresh conditions", exact: true }).click();
  await ready(page);
  await expect(page.getByTestId("tooth-svg-UR6")).toHaveAttribute("data-baseline-status", "unrecorded");
  await recordRoots(request, patientId, headers, { teeth: ["UR6"], condition: "filled_defective", apicectomy: true, expected_revisions: { UR6: 1 } });
  await page.getByTestId("tooth-label-UR6").click({ button: "right" });
  const toothConflict = nextSave(page, toothPath(patientId));
  await page.getByTestId("clinical-baseline-condition-reset").click();
  expect((await toothConflict).status()).toBe(409);
  await expect(page.getByTestId("clinical-baseline-error")).toContainText(/changed.*Refresh/i);
  expect((await snapshot(request, patientId, headers)).teeth.UR6.root_observations).toEqual(expectedRoots(3, "filled_defective", true));
  await page.getByRole("button", { name: "Refresh conditions", exact: true }).click();
  await ready(page);
  await rootDrawing(page, "UR6", 3, "filled_defective", true, true);
});

test("a pending or failed root batch cannot duplicate save or optimistically redraw teeth", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "Root area pending failure");
  await openChart(page, patientId);
  const writes = observeWrites(page, patientId);
  let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route(`**${rootPath(patientId)}`, async (route) => {
    await gate;
    await route.fulfill({ status: 500, contentType: "text/html", body: "<html>synthetic private infrastructure diagnostic</html>" });
  });
  await selectRoots(page, "post_core_sound", ["UR6", "LR6"]);
  const response = nextSave(page, rootPath(patientId));
  try {
    await page.getByTestId("root-diagnosis-apply").click();
    await expect(page.getByTestId("clinical-baseline-status")).toContainText(/saving/i);
    await expect(page.getByTestId("root-diagnosis-palette-filled_sound")).toBeDisabled();
    await expect(page.getByTestId("root-diagnosis-apply")).toBeDisabled();
    await expect(page.getByTestId("root-diagnosis-back")).toBeDisabled();
    await expect(page.getByTestId("root-diagnosis-cancel")).toBeDisabled();
    await page.getByTestId("clinical-root-UR6").click({ button: "right" });
    await expect(page.getByTestId("clinical-root-action-menu")).toHaveCount(0);
    await expect(page.getByTestId("clinical-root-UR6")).toHaveAttribute("data-root-selected", "true");
    await expect(page.getByTestId("clinical-root-LR6")).toHaveAttribute("data-root-selected", "true");
    await rootDrawing(page, "UR6", 3, null, false, false);
    await rootDrawing(page, "LR6", 2, null, false, false);
    expect(writes.roots).toHaveLength(1);
    expect(writes.teeth).toEqual([]);
    expect((await snapshot(request, patientId, headers)).teeth).toEqual({});
  } finally { release(); }
  expect((await response).status()).toBe(500);
  await expect(page.getByTestId("clinical-baseline-error")).toContainText(/could not be confirmed/i);
  await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/saved/i);
  await expect(page.getByText("synthetic private infrastructure diagnostic")).toHaveCount(0);
  expect((await snapshot(request, patientId, headers)).teeth).toEqual({});
  await rootDrawing(page, "UR6", 3, null, false, false);
  await page.unroute(`**${rootPath(patientId)}`);
  await page.getByRole("button", { name: "Refresh conditions", exact: true }).click();
  await ready(page);
  await page.getByTestId("root-diagnosis-cancel").click();
  await selectRoots(page, "post_core_sound", ["UR6", "LR6"]);
  expect(await applyRoots(page, patientId)).toEqual({ teeth: ["UR6", "LR6"], condition: "post_core_sound", expected_revisions: { UR6: 0, LR6: 0 } });
  await rootDrawing(page, "UR6", 3, "post_core_sound", false, true);
  await rootDrawing(page, "LR6", 2, "post_core_sound", false, true);
  expect(writes.roots).toHaveLength(2);
  expect(writes.teeth).toEqual([]);
  expect(writes.other).toEqual([]);
});

test("whole-root palette and context menu stay legible in light dark and compact layouts", async ({ page, request }, testInfo) => {
  const { patientId, headers } = await setup(page, request, "Whole root visual preview");
  for (const [index, tooth] of ["UR6", "UL6", "LR6", "LL6"].entries()) {
    await recordRoots(request, patientId, headers, { teeth: [tooth], condition: rootChoices[index].condition, apicectomy: index % 2 === 1, expected_revisions: { [tooth]: 0 } });
  }
  await openChart(page, patientId);
  const writes = observeWrites(page, patientId);
  await page.emulateMedia({ reducedMotion: "no-preference" });
  const target = page.getByTestId("clinical-root-UR6");
  await target.hover();
  await expect(target.locator(".clinical-root-halo").first()).not.toHaveCSS("animation-name", "none");
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(target.locator(".clinical-root-halo").first()).toHaveCSS("animation-name", "none");
  await selectRoots(page, "filled_sound", ["UR6", "LR6"]);
  const capture = async (name: string) => {
    await page.evaluate(() => { window.scrollTo(0, 0); return new Promise<void>((resolve) => requestAnimationFrame(() => resolve())); });
    const path = testInfo.outputPath(`${name}.png`);
    await page.screenshot({ path, fullPage: true });
    await testInfo.attach(name, { path, contentType: "image/png" });
  };
  const expectMenuStyle = async () => {
    const menu = page.getByTestId("clinical-root-action-menu");
    for (const choice of rootChoices) {
      await expect(menu.getByTestId(`clinical-root-condition-${choice.condition}`)).toHaveCSS("font-size", "18px");
      await expect(menu.getByTestId(`clinical-root-condition-${choice.condition}`)).toHaveCSS("gap", "10px");
    }
    const selected = menu.getByTestId("clinical-root-condition-filled_defective");
    await expect(selected).toHaveAttribute("aria-checked", "true");
    await expect(selected).toHaveCSS("border-left-color", "rgb(11, 158, 192)");
    await expect(menu.getByTestId("clinical-root-apicectomy")).toHaveAttribute("aria-checked", "true");
  };
  await capture("root-diagnosis-light");
  await page.getByRole("button", { name: "Toggle theme", exact: true }).click();
  await capture("root-diagnosis-dark");
  await openRootMenu(page, "UL6");
  await expectMenuStyle();
  const darkMenu = testInfo.outputPath("root-diagnosis-dark-menu.png");
  await page.screenshot({ path: darkMenu });
  await testInfo.attach("root-diagnosis-dark-menu", { path: darkMenu, contentType: "image/png" });
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Toggle theme", exact: true }).click();
  await page.getByTestId("root-diagnosis-cancel").click();
  await selectRoots(page, "filled_sound", ["UR6", "LR6"]);
  await page.setViewportSize({ width: 1900, height: 1900 });
  await capture("root-diagnosis-wide");
  const selectedChart = await page.getByTestId("clinical-chart").boundingBox();
  const palette = await page.getByTestId("clinical-root-diagnosis-palette").boundingBox();
  expect(selectedChart).not.toBeNull();
  expect(palette).not.toBeNull();
  await expect(page.getByTestId("clinical-root-UR6")).toHaveAttribute("data-root-selected", "true");
  await expect(page.getByTestId("clinical-root-LR6")).toHaveAttribute("data-root-selected", "true");
  const paletteX = Math.max(0, Math.min(selectedChart!.x, palette!.x) - 10);
  const paletteY = Math.max(0, selectedChart!.y - 10);
  const paletteRight = Math.max(selectedChart!.x + selectedChart!.width, palette!.x + palette!.width) + 10;
  const paletteBottom = palette!.y + palette!.height + 10;
  expect(paletteRight).toBeLessThanOrEqual(1900);
  expect(paletteBottom).toBeLessThanOrEqual(1900);
  const paletteCloseup = testInfo.outputPath("root-diagnosis-chart-palette-closeup.png");
  await page.screenshot({ path: paletteCloseup, clip: { x: paletteX, y: paletteY, width: paletteRight - paletteX, height: paletteBottom - paletteY } });
  await testInfo.attach("root-diagnosis-chart-palette-closeup", { path: paletteCloseup, contentType: "image/png" });
  await page.setViewportSize({ width: 1900, height: 1400 });
  await page.evaluate(() => { window.scrollTo(0, 0); return new Promise<void>((resolve) => requestAnimationFrame(() => resolve())); });
  await openRootMenu(page, "UL6");
  await expectMenuStyle();
  const chart = await page.getByTestId("clinical-chart").boundingBox();
  const menu = await page.getByTestId("clinical-root-action-menu").boundingBox();
  expect(chart).not.toBeNull();
  expect(menu).not.toBeNull();
  const x = Math.max(0, Math.min(chart!.x, menu!.x) - 10);
  const y = Math.max(0, Math.min(chart!.y, menu!.y) - 10);
  const right = Math.max(chart!.x + chart!.width, menu!.x + menu!.width) + 10;
  const bottom = Math.max(chart!.y + chart!.height, menu!.y + menu!.height) + 10;
  expect(right).toBeLessThanOrEqual(1900);
  expect(bottom).toBeLessThanOrEqual(1400);
  const closeup = testInfo.outputPath("root-diagnosis-chart-menu-closeup.png");
  await page.screenshot({ path: closeup, clip: { x, y, width: right - x, height: bottom - y } });
  await testInfo.attach("root-diagnosis-chart-menu-closeup", { path: closeup, contentType: "image/png" });
  await page.keyboard.press("Escape");
  await page.setViewportSize({ width: 390, height: 844 });
  await openRootMenu(page, "UL6");
  const mobileBounds = await page.getByTestId("clinical-root-action-menu").boundingBox();
  expect(mobileBounds!.x).toBeGreaterThanOrEqual(0);
  expect(mobileBounds!.x + mobileBounds!.width).toBeLessThanOrEqual(390);
  expect(mobileBounds!.y + mobileBounds!.height).toBeLessThanOrEqual(844);
  await expect(page.getByTestId("clinical-root-reset")).toBeVisible();
  const mobileMenu = testInfo.outputPath("root-diagnosis-mobile-menu.png");
  await page.screenshot({ path: mobileMenu });
  await testInfo.attach("root-diagnosis-mobile-menu", { path: mobileMenu, contentType: "image/png" });
  await page.keyboard.press("Escape");
  await capture("root-diagnosis-mobile");
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(391);
  expect(writes.roots).toEqual([]);
  expect(writes.teeth).toEqual([]);
  expect(writes.other).toEqual([]);
});
