import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import { addInvoiceLine, createInvoice, createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

const actionIds = [
  "missing", "deciduous", "implant", "unerupted", "impacted", "present",
  "movement_forward", "movement_backward", "rotation_clockwise", "rotation_anticlockwise",
  "reset",
] as const;
type ActionId = typeof actionIds[number];
type Condition = "present" | "missing" | "deciduous" | "implant" | "unerupted" | "impacted" | "unrecorded";
type Observation = {
  condition: Condition | null;
  movement?: "forward" | "backward" | null;
  rotation?: "clockwise" | "anticlockwise" | null;
  revision: number;
};
type Snapshot = { patient_id: number; teeth: Record<string, Observation>; note_teeth: string[] };
type Mutation = {
  teeth: string[];
  expected_revisions: Record<string, number>;
  condition?: Condition | null;
  movement?: "forward" | "backward" | null;
  rotation?: "clockwise" | "anticlockwise" | null;
};

function conditionsPath(patientId: string) {
  return `/api/patients/${patientId}/clinical/tooth-conditions`;
}

async function setup(page: Page, request: APIRequestContext, title: string) {
  const token = await primePageAuth(page, request);
  const patientId = await createPatient(request, { first_name: "Synthetic", last_name: `${title} ${Date.now()}` });
  return { token, patientId, headers: { Authorization: `Bearer ${token}` } };
}

async function snapshot(request: APIRequestContext, patientId: string, token: string): Promise<Snapshot> {
  const response = await request.get(`${getBaseUrl()}${conditionsPath(patientId)}`, { headers: { Authorization: `Bearer ${token}` } });
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function openChart(page: Page, patientId: string) {
  await page.goto(`${getBaseUrl()}/patients/${patientId}/clinical?clinicalView=current`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/loading/i);
  await expect(page.getByTestId("clinical-diagnosis-palette")).toBeVisible();
}

async function openMenu(page: Page, tooth: string) {
  await page.getByTestId(`tooth-label-${tooth}`).click({ button: "right" });
  await expect(page.getByTestId("clinical-tooth-action-menu")).toBeVisible();
}

function observeWrites(page: Page, patientId: string) {
  const bodies: Mutation[] = [];
  const otherClinicalWrites: string[] = [];
  page.on("request", (request) => {
    if (!["POST", "PATCH", "PUT", "DELETE"].includes(request.method())) return;
    const path = new URL(request.url()).pathname;
    if (path === conditionsPath(patientId)) bodies.push(request.postDataJSON() as Mutation);
    else if (/\/api\/(?:patients|invoices|payments|treatment)/.test(path)) otherClinicalWrites.push(path);
  });
  return { bodies, otherClinicalWrites };
}

async function chooseTargets(page: Page, action: ActionId, teeth: string[]) {
  await page.getByTestId(`diagnosis-palette-${action}`).click();
  await expect(page.getByTestId(`diagnosis-palette-${action}`)).toHaveAttribute("aria-pressed", "true");
  for (const tooth of teeth) {
    await page.getByTestId(`tooth-label-${tooth}`).click();
    await expect(page.getByTestId(`tooth-button-${tooth}`)).toHaveAttribute("data-batch-selected", "true");
  }
}

function nextSave(page: Page, patientId: string) {
  return page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === conditionsPath(patientId));
}

async function applyBatch(page: Page, patientId: string) {
  const saved = nextSave(page, patientId);
  await page.getByTestId("diagnosis-apply").click();
  const response = await saved;
  expect(response.ok()).toBeTruthy();
  await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/saving/i);
  return response.request().postDataJSON() as Mutation;
}

async function expectCleared(page: Page) {
  await expect(page.locator('[data-testid^="tooth-button-"][data-batch-selected="true"]')).toHaveCount(0);
  await expect(page.getByTestId("clinical-diagnosis-palette").locator('[aria-pressed="true"]')).toHaveCount(0);
  await expect(page.getByTestId("diagnosis-apply")).toBeDisabled();
}

async function expectPaletteSizing(page: Page) {
  for (const action of actionIds) {
    const tile = page.getByTestId(`diagnosis-palette-${action}`);
    await expect(tile).toHaveCSS("font-size", "18px");
    const icon = tile.locator("svg.clinical-diagnosis-symbol");
    await expect(icon).toHaveCount(1);
    await expect(icon).toHaveAttribute("data-diagnosis-icon", action);
    await expect(icon).toHaveCSS("width", "34.5px");
    await expect(icon).toHaveCSS("height", "34.5px");
    const tileBox = await tile.boundingBox();
    const iconBox = await icon.boundingBox();
    expect(tileBox).not.toBeNull();
    expect(iconBox).not.toBeNull();
    expect(Math.abs(iconBox!.x + iconBox!.width / 2 - tileBox!.x - tileBox!.width / 2), `${action} icon is centred`).toBeLessThanOrEqual(1);
    const dimensions = await tile.evaluate((element) => ({ width: element.clientWidth, contentWidth: element.scrollWidth, height: element.clientHeight, contentHeight: element.scrollHeight }));
    expect(dimensions.contentWidth, `${action} text fits its tile`).toBeLessThanOrEqual(dimensions.width + 1);
    expect(dimensions.contentHeight, `${action} icon and label fit vertically`).toBeLessThanOrEqual(dimensions.height + 1);
  }
}

test("Current chart palette and tooth-number menu expose the same diagnosis-only choices", async ({ page, request }) => {
  const { patientId } = await setup(page, request, "Diagnosis choices");
  await openChart(page, patientId);
  const { bodies, otherClinicalWrites } = observeWrites(page, patientId);
  const palette = page.getByTestId("clinical-diagnosis-palette");
  await expect(palette.locator('[data-testid^="diagnosis-palette-"]')).toHaveCount(11);
  await expectPaletteSizing(page);
  for (const action of actionIds) await expect(palette.getByTestId(`diagnosis-palette-${action}`)).toBeVisible();
  for (const oldAction of ["clear_movement", "clear_rotation", "unrecorded"]) await expect(palette.getByTestId(`diagnosis-palette-${oldAction}`)).toHaveCount(0);
  await expect(palette.getByTestId("diagnosis-palette-reset")).toHaveAccessibleName("Reset the tooth");
  await expect(page.getByTestId("diagnosis-apply")).toBeDisabled();
  await openMenu(page, "UR5");
  await expect(page.getByTestId("clinical-tooth-action-menu").locator('[data-testid^="clinical-baseline-condition-"]')).toHaveCount(11);
  for (const action of actionIds) await expect(page.getByTestId(`clinical-baseline-condition-${action}`)).toBeVisible();
  for (const oldAction of ["clear_movement", "clear_rotation", "unrecorded"]) await expect(page.getByTestId(`clinical-baseline-condition-${oldAction}`)).toHaveCount(0);
  await expect(page.getByTestId("clinical-chart-menu-add-procedure")).toHaveCount(0);
  await expect(page.getByTestId("clinical-chart-menu-add-plan")).toHaveCount(0);
  await expect(page.getByTestId("clinical-chart-menu-add-note")).toBeVisible();
  await expect(page.getByTestId("clinical-chart-menu-view-timeline")).toBeVisible();
  await page.keyboard.press("Escape");

  // Surface diagnosis replaces the tooth palette, never opening treatment tools.
  await page.getByTestId("tooth-surface-UR5-M").click();
  await page.getByTestId("tooth-surface-UR5-D").click({ button: "right" });
  await expect(page.getByTestId("clinical-surface-action-menu")).toBeVisible();
  await expect(page.getByTestId("clinical-surface-diagnosis-palette")).toBeVisible();
  await expect(page.getByTestId("clinical-diagnosis-palette")).toHaveCount(0);
  await expect(page.getByTestId("clinical-surface-selection")).toContainText("UR5 MD");
  await expect(page.getByTestId("clinical-chart-menu-add-procedure")).toHaveCount(0);
  await expect(page.getByTestId("clinical-chart-menu-add-plan")).toHaveCount(0);
  expect(bodies).toEqual([]);
  expect(otherClinicalWrites).toEqual([]);
});

test("diagnosis selection waits for Apply, supports toggling and changing tools, and never bills treatment", async ({ page, request }) => {
  const { patientId, token, headers } = await setup(page, request, "Diagnosis batch");
  const financeBefore = await request.get(`${getBaseUrl()}/api/patients/${patientId}/finance-summary`, { headers });
  expect(financeBefore.ok()).toBeTruthy();
  const originalFinance = await financeBefore.json();
  await openChart(page, patientId);
  const { bodies, otherClinicalWrites } = observeWrites(page, patientId);

  await chooseTargets(page, "implant", ["UR5", "UR6", "LL6"]);
  await page.getByTestId("tooth-label-UR6").click();
  await expect(page.getByTestId("tooth-button-UR6")).not.toHaveAttribute("data-batch-selected", "true");
  await page.getByTestId("diagnosis-palette-missing").click();
  await expect(page.getByTestId("tooth-button-UR5")).toHaveAttribute("data-batch-selected", "true");
  await expect(page.getByTestId("tooth-button-LL6")).toHaveAttribute("data-batch-selected", "true");
  await expect(page.getByTestId("diagnosis-palette-missing")).toHaveAttribute("aria-pressed", "true");
  expect(bodies).toEqual([]);
  expect((await snapshot(request, patientId, token)).teeth).toEqual({});
  await expect(page.getByTestId("tooth-crown-UR5")).toBeAttached();

  const body = await applyBatch(page, patientId);
  expect(body).toEqual({ teeth: expect.arrayContaining(["UR5", "LL6"]), condition: "missing", expected_revisions: { UR5: 0, LL6: 0 } });
  expect(body.teeth).toHaveLength(2);
  expect(bodies).toHaveLength(1);
  const stored = await snapshot(request, patientId, token);
  expect(Object.keys(stored.teeth).sort()).toEqual(["LL6", "UR5"]);
  expect(stored.teeth.UR5).toMatchObject({ condition: "missing", revision: 1 });
  expect(stored.teeth.LL6).toMatchObject({ condition: "missing", revision: 1 });
  await expect(page.getByTestId("tooth-crown-UR5")).toHaveCount(0);
  await expect(page.getByTestId("tooth-crown-LL6")).toHaveCount(0);
  await expect(page.getByTestId("tooth-crown-UR6")).toBeAttached();
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("tooth-svg-UR5")).toHaveAttribute("data-baseline-status", "missing");
  await expect(page.getByTestId("tooth-svg-LL6")).toHaveAttribute("data-baseline-status", "missing");

  const clinical = await request.get(`${getBaseUrl()}/api/patients/${patientId}/clinical/summary`, { headers });
  expect(clinical.ok()).toBeTruthy();
  expect(await clinical.json()).toMatchObject({ recent_procedures: [], treatment_plan_items: [], recent_tooth_notes: [] });
  const financeAfter = await request.get(`${getBaseUrl()}/api/patients/${patientId}/finance-summary`, { headers });
  expect(financeAfter.ok()).toBeTruthy();
  expect(await financeAfter.json()).toEqual(originalFinance);
  expect(otherClinicalWrites).toEqual([]);
});

test("movement and rotation update only their own field and repeat the same action from the number menu", async ({ page, request }) => {
  const { patientId, token, headers } = await setup(page, request, "Diagnosis axes");
  const seeded = await request.post(`${getBaseUrl()}${conditionsPath(patientId)}`, { headers, data: { teeth: ["UR5"], condition: "implant", expected_revisions: { UR5: 0 } } });
  expect(seeded.ok()).toBeTruthy();
  await openChart(page, patientId);
  const { bodies } = observeWrites(page, patientId);
  const actions: Array<{ id: ActionId; field: "movement" | "rotation"; value: string | null }> = [
    { id: "movement_forward", field: "movement", value: "forward" },
    { id: "movement_backward", field: "movement", value: "backward" },
    { id: "rotation_clockwise", field: "rotation", value: "clockwise" },
    { id: "rotation_anticlockwise", field: "rotation", value: "anticlockwise" },
  ];
  let revision = 1;
  for (const action of actions) {
    await expectCleared(page);
    await chooseTargets(page, action.id, ["UR5"]);
    const body = await applyBatch(page, patientId);
    expect(body).toEqual({ teeth: ["UR5"], expected_revisions: { UR5: revision }, [action.field]: action.value });
    revision += 1;
    const stored = await snapshot(request, patientId, token);
    expect(stored.teeth.UR5).toMatchObject({ condition: "implant", [action.field]: action.value, revision });
    await expect(page.getByTestId("tooth-baseline-implant-UR5")).toBeAttached();
  }
  expect(bodies).toHaveLength(actions.length);
  await expectCleared(page);
  await openMenu(page, "LL6");
  const saved = nextSave(page, patientId);
  await page.getByTestId("clinical-baseline-condition-movement_forward").click();
  expect((await saved).ok()).toBeTruthy();
  await openMenu(page, "LR6");
  await expect(page.getByTestId("clinical-baseline-repeat")).toBeEnabled();
  const repeated = nextSave(page, patientId);
  await page.getByTestId("clinical-baseline-repeat").click();
  const repeatedResponse = await repeated;
  expect(repeatedResponse.ok()).toBeTruthy();
  expect(repeatedResponse.request().postDataJSON()).toEqual({ teeth: ["LR6"], movement: "forward", expected_revisions: { LR6: 0 } });
  const stored = await snapshot(request, patientId, token);
  expect(stored.teeth.LR6).toMatchObject({ condition: null, movement: "forward", revision: 1 });
});

test("single and batch tooth reset clear observations without losing notes history or finances", async ({ page, request }) => {
  const { patientId, token, headers } = await setup(page, request, "Diagnosis reset retention");
  const endpoint = `${getBaseUrl()}${conditionsPath(patientId)}`;
  const primary = await request.post(endpoint, { headers, data: { teeth: ["UR5", "LL5"], condition: "deciduous", movement: "forward", rotation: "clockwise", expected_revisions: { UR5: 0, LL5: 0 } } });
  expect(primary.ok()).toBeTruthy();
  const implant = await request.post(endpoint, { headers, data: { teeth: ["UR6"], condition: "implant", movement: "backward", rotation: "anticlockwise", expected_revisions: { UR6: 0 } } });
  expect(implant.ok()).toBeTruthy();
  for (const tooth of ["UR5", "LL5"]) {
    const note = await request.post(`${getBaseUrl()}/api/patients/${patientId}/tooth-notes`, { headers, data: { tooth, surface: null, note: `Synthetic retained observation on ${tooth}` } });
    expect(note.ok()).toBeTruthy();
  }
  const procedure = await request.post(`${getBaseUrl()}/api/patients/${patientId}/procedures`, { headers, data: { tooth: "UR5", procedure_code: "RESET_PROOF", description: "Synthetic earlier completed treatment retained during reset", fee_pence: 1200 } });
  expect(procedure.ok()).toBeTruthy();
  const invoice = await createInvoice(request, patientId, { notes: "Synthetic reset retention invoice" });
  await addInvoiceLine(request, invoice.id, { description: "Synthetic recorded charge", quantity: 1, unit_price_pence: 15000 });
  const historyBefore: Record<string, unknown> = {};
  for (const tooth of ["UR5", "LL5"]) {
    const history = await request.get(`${getBaseUrl()}/api/patients/${patientId}/tooth-history?tooth=${tooth}`, { headers });
    expect(history.ok()).toBeTruthy();
    historyBefore[tooth] = await history.json();
  }
  const financeBefore = await request.get(`${getBaseUrl()}/api/patients/${patientId}/finance-summary`, { headers });
  expect(financeBefore.ok()).toBeTruthy();
  const recordedFinance = await financeBefore.json();
  const invoiceBefore = await request.get(`${getBaseUrl()}/api/invoices/${invoice.id}`, { headers });
  expect(invoiceBefore.ok()).toBeTruthy();
  const recordedInvoice = await invoiceBefore.json();

  await openChart(page, patientId);
  const { bodies, otherClinicalWrites } = observeWrites(page, patientId);
  await expect(page.getByTestId("tooth-label-UR5")).toHaveText("URE");
  await expect(page.getByTestId("tooth-label-LL5")).toHaveText("LLE");
  await expect(page.getByTestId("tooth-note-flag-UR5")).toBeVisible();
  await openMenu(page, "UR5");
  const singleSaved = nextSave(page, patientId);
  await page.getByTestId("clinical-baseline-condition-reset").click();
  const singleResponse = await singleSaved;
  expect(singleResponse.ok()).toBeTruthy();
  expect(singleResponse.request().postDataJSON()).toEqual({ teeth: ["UR5"], condition: "unrecorded", movement: null, rotation: null, expected_revisions: { UR5: 1 } });
  await expect(page.getByTestId("tooth-label-UR5")).toHaveText("UR5");
  await expect(page.getByTestId("tooth-svg-UR5")).toHaveAttribute("data-baseline-status", "unrecorded");
  await expect(page.getByTestId("tooth-svg-UR5")).not.toHaveAttribute("data-baseline-status", "present");
  await expect(page.getByTestId("tooth-note-flag-UR5")).toBeVisible();
  await openMenu(page, "LL5");
  await expect(page.getByTestId("clinical-baseline-repeat")).toBeEnabled();
  await expect(page.getByTestId("clinical-baseline-repeat")).toContainText("Reset the tooth");
  await page.keyboard.press("Escape");

  await chooseTargets(page, "reset", ["LL5", "UR6"]);
  expect(bodies).toHaveLength(1);
  await expect(page.getByTestId("tooth-label-LL5")).toHaveText("LLE");
  await expect(page.getByTestId("tooth-baseline-implant-UR6")).toBeAttached();
  const batch = await applyBatch(page, patientId);
  expect(batch).toEqual({ teeth: ["LL5", "UR6"], condition: "unrecorded", movement: null, rotation: null, expected_revisions: { LL5: 1, UR6: 1 } });
  expect(bodies).toHaveLength(2);
  for (const tooth of ["UR5", "LL5", "UR6"]) {
    await expect(page.getByTestId(`tooth-svg-${tooth}`)).toHaveAttribute("data-baseline-status", "unrecorded");
    await expect(page.getByTestId(`tooth-label-${tooth}`)).toHaveText(tooth);
    await expect(page.getByTestId(`tooth-baseline-implant-${tooth}`)).toHaveCount(0);
    await expect(page.getByTestId(`tooth-crown-${tooth}`)).toBeAttached();
  }
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/loading/i);
  const stored = await snapshot(request, patientId, token);
  for (const tooth of ["UR5", "LL5", "UR6"]) {
    expect(stored.teeth[tooth]).toMatchObject({ condition: "unrecorded", movement: null, rotation: null, revision: 2 });
    await expect(page.getByTestId(`tooth-label-${tooth}`)).toHaveText(tooth);
    await expect(page.getByTestId(`tooth-svg-${tooth}`)).toHaveAttribute("data-baseline-status", "unrecorded");
  }
  expect(stored.note_teeth.sort()).toEqual(["LL5", "UR5"]);
  for (const tooth of ["UR5", "LL5"]) {
    await expect(page.getByTestId(`tooth-note-flag-${tooth}`)).toBeVisible();
    const history = await request.get(`${getBaseUrl()}/api/patients/${patientId}/tooth-history?tooth=${tooth}`, { headers });
    expect(history.ok()).toBeTruthy();
    expect(await history.json()).toEqual(historyBefore[tooth]);
  }
  const financeAfter = await request.get(`${getBaseUrl()}/api/patients/${patientId}/finance-summary`, { headers });
  expect(financeAfter.ok()).toBeTruthy();
  expect(await financeAfter.json()).toEqual(recordedFinance);
  const invoiceAfter = await request.get(`${getBaseUrl()}/api/invoices/${invoice.id}`, { headers });
  expect(invoiceAfter.ok()).toBeTruthy();
  expect(await invoiceAfter.json()).toEqual(recordedInvoice);
  expect(otherClinicalWrites).toEqual([]);
});

test("reset suppresses legacy restoration drawings only in Current and remains unrecorded after another observation", async ({ page, request }) => {
  const { patientId, token } = await setup(page, request, "Diagnosis reset legacy display");
  // Synthetic persisted-import representation only: no R4 connection or records.
  const legacy = {
    patient_id: Number(patientId), legacy_patient_code: null,
    teeth: { "15": { missing: true, extracted: true, restorations: [
      { type: "crown", surfaces: [], meta: { source: "synthetic-test", code_label: "Synthetic historical crown" } },
      { type: "root_canal", surfaces: [], meta: { source: "synthetic-test", code_label: "Synthetic historical root treatment" } },
    ] } },
  };
  await page.route(`**/api/patients/${patientId}/charting/tooth-state*`, (route) => route.fulfill({ json: legacy }));
  await openChart(page, patientId);
  await expect(page.getByTestId("tooth-restoration-UR5-missing")).toBeAttached();
  await expect(page.getByTestId("tooth-anatomy-restoration-UR5-crown")).toBeAttached();
  await openMenu(page, "UR5");
  const reset = nextSave(page, patientId);
  await page.getByTestId("clinical-baseline-condition-reset").click();
  expect((await reset).ok()).toBeTruthy();
  await expect(page.getByTestId("tooth-svg-UR5")).toHaveAttribute("data-baseline-status", "unrecorded");
  await expect(page.locator('[data-testid^="tooth-restoration-UR5-"], [data-testid^="tooth-anatomy-restoration-UR5-"]')).toHaveCount(0);
  await expect(page.getByTestId("tooth-crown-UR5")).toBeAttached();

  await chooseTargets(page, "movement_forward", ["UR5"]);
  expect(await applyBatch(page, patientId)).toEqual({ teeth: ["UR5"], movement: "forward", expected_revisions: { UR5: 1 } });
  expect((await snapshot(request, patientId, token)).teeth.UR5).toMatchObject({ condition: "unrecorded", movement: "forward", rotation: null, revision: 2 });
  await expect(page.locator('[data-testid^="tooth-restoration-UR5-"], [data-testid^="tooth-anatomy-restoration-UR5-"]')).toHaveCount(0);
  await page.getByTestId("clinical-chart-view-history").click();
  await expect(page.getByTestId("tooth-restoration-UR5-missing")).toBeAttached();
  await expect(page.getByTestId("tooth-anatomy-restoration-UR5-crown")).toBeAttached();
  await expect(page.getByTestId("tooth-anatomy-restoration-UR5-root_canal")).toBeAttached();
  await page.getByTestId("clinical-chart-view-current").click();
  await expect(page.getByTestId("tooth-svg-UR5")).toHaveAttribute("data-baseline-status", "unrecorded");
  await expect(page.locator('[data-testid^="tooth-restoration-UR5-"], [data-testid^="tooth-anatomy-restoration-UR5-"]')).toHaveCount(0);
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("tooth-svg-UR5")).toHaveAttribute("data-baseline-status", "unrecorded");
  await expect(page.locator('[data-testid^="tooth-restoration-UR5-"], [data-testid^="tooth-anatomy-restoration-UR5-"]')).toHaveCount(0);
});

test("Cancel and patient tab or view changes discard unsaved diagnosis selection", async ({ page, request }) => {
  const { patientId, token } = await setup(page, request, "Diagnosis boundaries");
  await openChart(page, patientId);
  const { bodies } = observeWrites(page, patientId);
  await chooseTargets(page, "missing", ["UR5", "LL6"]);
  await page.getByTestId("diagnosis-cancel").click();
  await expectCleared(page);

  await chooseTargets(page, "implant", ["UR5"]);
  await page.getByTestId("clinical-chart-view-planned").click();
  await expect(page.getByTestId("clinical-diagnosis-palette")).toHaveCount(0);
  await page.getByTestId("clinical-chart-view-current").click();
  await expectCleared(page);
  await chooseTargets(page, "missing", ["UR5"]);
  await page.getByTestId("patient-tab-Personal").click();
  await expect(page.getByTestId("clinical-diagnosis-palette")).toHaveCount(0);
  await page.getByTestId("patient-tab-Medical").click();
  await expect(page.getByTestId("clinical-diagnosis-palette")).toBeVisible();
  await expectCleared(page);

  await chooseTargets(page, "missing", ["UR5"]);
  const nextPatient = await createPatient(request, { first_name: "Synthetic", last_name: `Diagnosis next patient ${Date.now()}` });
  await openChart(page, nextPatient);
  await expectCleared(page);
  expect(bodies).toEqual([]);
  expect((await snapshot(request, patientId, token)).teeth).toEqual({});
  expect((await snapshot(request, nextPatient, token)).teeth).toEqual({});
});

test("a pending diagnosis batch is locked and repeated Apply cannot duplicate the request", async ({ page, request }) => {
  const { patientId, token } = await setup(page, request, "Diagnosis pending");
  await openChart(page, patientId);
  let release!: () => void;
  const pending = new Promise<void>((resolve) => { release = resolve; });
  let started!: () => void;
  const seen = new Promise<void>((resolve) => { started = resolve; });
  const { bodies } = observeWrites(page, patientId);
  await page.route(`**${conditionsPath(patientId)}`, async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    started();
    await pending;
    await route.continue();
  });
  try {
    await chooseTargets(page, "missing", ["UR5", "LL6"]);
    const saved = nextSave(page, patientId);
    await page.getByTestId("diagnosis-apply").evaluate((element) => {
      const button = element as HTMLButtonElement;
      button.click();
      button.click();
    });
    await seen;
    await expect(page.getByTestId("clinical-baseline-status")).toContainText(/saving/i);
    await expect(page.getByTestId("diagnosis-apply")).toBeDisabled();
    await expect(page.getByTestId("diagnosis-palette-implant")).toBeDisabled();
    await expect(page.getByTestId("tooth-crown-UR5")).toBeAttached();
    expect(bodies).toHaveLength(1);
    release();
    expect((await saved).ok()).toBeTruthy();
    await expect(page.getByTestId("tooth-crown-UR5")).toHaveCount(0);
    expect((await snapshot(request, patientId, token)).teeth.UR5).toMatchObject({ condition: "missing", revision: 1 });
  } finally {
    release();
  }
});

test("failed and stale diagnosis batches preserve known findings and require refresh before another Apply", async ({ page, request }) => {
  const { patientId, token, headers } = await setup(page, request, "Diagnosis rejected");
  const seeded = await request.post(`${getBaseUrl()}${conditionsPath(patientId)}`, { headers, data: { teeth: ["UR5"], condition: "missing", expected_revisions: { UR5: 0 } } });
  expect(seeded.ok()).toBeTruthy();
  await openChart(page, patientId);
  const routePattern = `**${conditionsPath(patientId)}`;
  await page.route(routePattern, (route) => route.request().method() === "POST"
    ? route.fulfill({ status: 500, contentType: "text/html", body: "<p>private synthetic diagnosis failure</p>" })
    : route.continue());
  await chooseTargets(page, "implant", ["UR5", "LL6"]);
  const failed = nextSave(page, patientId);
  await page.getByTestId("diagnosis-apply").click();
  expect((await failed).status()).toBe(500);
  await expect(page.getByTestId("clinical-baseline-error")).toBeVisible();
  await expect(page.getByText("private synthetic diagnosis failure")).toHaveCount(0);
  await expect(page.getByTestId("tooth-crown-UR5")).toHaveCount(0);
  await expect(page.getByTestId("tooth-crown-LL6")).toBeAttached();
  await expect(page.getByTestId("diagnosis-apply")).toBeDisabled();
  await expect(page.getByTestId("diagnosis-palette-implant")).toBeDisabled();
  await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/saved/i);
  await page.unroute(routePattern);
  await page.getByTestId("clinical-baseline-error").getByRole("button", { name: "Refresh conditions" }).click();
  await expect(page.getByTestId("clinical-baseline-error")).toHaveCount(0);
  await page.getByTestId("diagnosis-cancel").click();
  await chooseTargets(page, "implant", ["UR5", "LL6"]);
  const concurrent = await request.post(`${getBaseUrl()}${conditionsPath(patientId)}`, { headers, data: { teeth: ["LL6"], condition: "unerupted", expected_revisions: { LL6: 0 } } });
  expect(concurrent.ok()).toBeTruthy();
  const conflict = nextSave(page, patientId);
  await page.getByTestId("diagnosis-apply").click();
  expect((await conflict).status()).toBe(409);
  await expect(page.getByTestId("clinical-baseline-error")).toContainText(/changed|refresh/i);
  await expect(page.getByTestId("diagnosis-apply")).toBeDisabled();
  const stored = await snapshot(request, patientId, token);
  expect(stored.teeth.UR5).toMatchObject({ condition: "missing", revision: 1 });
  expect(stored.teeth.LL6).toMatchObject({ condition: "unerupted", revision: 1 });
  await expect(page.getByTestId("tooth-baseline-implant-UR5")).toHaveCount(0);
  await expect(page.getByTestId("tooth-baseline-implant-LL6")).toHaveCount(0);
});

test("read-only or unavailable baseline data cannot arm or apply a diagnosis batch", async ({ page, request }) => {
  const { patientId } = await setup(page, request, "Diagnosis permissions");
  await page.route("**/api/me/capabilities", (route) => route.fulfill({ json: ["patients.view", "clinical.view"] }));
  await openChart(page, patientId);
  const { bodies } = observeWrites(page, patientId);
  for (const action of actionIds) await expect(page.getByTestId(`diagnosis-palette-${action}`)).toBeDisabled();
  await expect(page.getByTestId("diagnosis-apply")).toBeDisabled();
  await openMenu(page, "UR5");
  for (const action of actionIds) await expect(page.getByTestId(`clinical-baseline-condition-${action}`)).toBeDisabled();
  await expect(page.getByTestId("clinical-chart-menu-view-timeline")).toBeEnabled();
  await page.keyboard.press("Escape");

  await page.unroute("**/api/me/capabilities");
  await page.route(`**${conditionsPath(patientId)}`, (route) => route.fulfill({ status: 503, contentType: "text/plain", body: "Synthetic conditions unavailable" }));
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("clinical-baseline-error")).toBeVisible();
  for (const action of actionIds) await expect(page.getByTestId(`diagnosis-palette-${action}`)).toBeDisabled();
  await expect(page.getByTestId("diagnosis-apply")).toBeDisabled();
  expect(bodies).toEqual([]);
});

test("saved deciduous teeth show British A to E labels without changing their stored numeric tooth identities", async ({ page, request }) => {
  const { patientId, token, headers } = await setup(page, request, "Diagnosis primary");
  const quadrants = ["UR", "UL", "LR", "LL"];
  const teeth = quadrants.flatMap((quadrant) => Array.from({ length: 5 }, (_, index) => `${quadrant}${index + 1}`));
  const seeded = await request.post(`${getBaseUrl()}${conditionsPath(patientId)}`, { headers, data: { teeth, condition: "deciduous", expected_revisions: Object.fromEntries(teeth.map((tooth) => [tooth, 0])) } });
  expect(seeded.ok()).toBeTruthy();
  await openChart(page, patientId);
  for (const quadrant of quadrants) {
    for (let position = 1; position <= 5; position += 1) {
      const tooth = `${quadrant}${position}`;
      await expect(page.getByTestId(`tooth-label-${tooth}`)).toHaveText(`${quadrant}${"ABCDE"[position - 1]}`);
      await expect(page.getByTestId(`tooth-svg-${tooth}`)).toHaveAttribute("data-dentition", "deciduous");
    }
    for (let position = 6; position <= 8; position += 1) await expect(page.getByTestId(`tooth-label-${quadrant}${position}`)).toHaveText(`${quadrant}${position}`);
  }
  await openMenu(page, "LR4");
  const saved = nextSave(page, patientId);
  await page.getByTestId("clinical-baseline-condition-present").click();
  const response = await saved;
  expect(response.ok()).toBeTruthy();
  expect(response.request().postDataJSON()).toEqual({ teeth: ["LR4"], condition: "present", expected_revisions: { LR4: 1 } });
  await expect(page.getByTestId("tooth-label-LR4")).toHaveText("LR4");
  await openMenu(page, "LR6");
  await expect(page.getByTestId("clinical-baseline-condition-deciduous")).toBeDisabled();
  await page.keyboard.press("Escape");
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/loading/i);
  await expect(page.getByTestId("tooth-label-LR5")).toHaveText("LRE");
  const stored = await snapshot(request, patientId, token);
  expect(Object.keys(stored.teeth).sort()).toEqual([...teeth].sort());
  expect(stored.teeth.LR4).toMatchObject({ condition: "present", revision: 2 });
  expect(Object.keys(stored.teeth).some((key) => /[A-E]$/.test(key))).toBe(false);
});

test("a Planned surface selection cannot silently attach a surface or procedure to a Current whole-tooth note", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "Diagnosis note boundary");
  await openChart(page, patientId);
  await page.getByTestId("clinical-chart-view-planned").click();
  await expect(page.getByTestId("clinical-chart-view-planned")).toHaveAttribute("aria-pressed", "true");
  await page.getByTestId("tooth-surface-UR5-M").click();
  await expect(page.getByTestId("tooth-surface-UR5-M")).toHaveAttribute("data-selected", "true");
  await expect(page.getByTestId("patient-chart-note-surface")).toHaveValue("M");

  // Do not reselect/right-click the tooth here: that would clear the stale
  // surface independently and fail to exercise the view-boundary safeguard.
  await page.getByTestId("clinical-chart-view-current").click();
  await expect(page.getByTestId("clinical-diagnosis-palette")).toBeVisible();
  await page.getByTestId("clinical-diagnosis-palette").getByRole("button", { name: "Add tooth note", exact: true }).click();
  await expect(page.getByTestId("patient-chart-note-body")).toBeFocused();
  await expect(page.getByTestId("patient-chart-note-surface")).toHaveCount(0);
  for (const id of ["patient-chart-procedure-code", "patient-chart-procedure-description", "patient-chart-procedure-fee", "patient-chart-procedure-add"]) {
    await expect(page.getByTestId(id)).toHaveCount(0);
  }
  const note = `Synthetic whole-tooth diagnosis note ${Date.now()}`;
  await page.getByTestId("patient-chart-note-body").fill(note);
  const saved = page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === `/api/patients/${patientId}/tooth-notes`);
  await page.getByTestId("patient-chart-note-add").click();
  const response = await saved;
  expect(response.ok()).toBeTruthy();
  expect(response.request().postDataJSON()).toEqual({ tooth: "UR5", surface: null, note });
  const history = await request.get(`${getBaseUrl()}/api/patients/${patientId}/tooth-history?tooth=UR5`, { headers });
  expect(history.ok()).toBeTruthy();
  expect(await history.json()).toMatchObject({ notes: [expect.objectContaining({ tooth: "UR5", surface: null, note })], procedures: [] });
});

test("tooth-number hover pulse never resizes anatomy and is disabled by reduced motion", async ({ page, request }) => {
  const { patientId } = await setup(page, request, "Diagnosis hover");
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await openChart(page, patientId);
  const label = page.getByTestId("tooth-label-UR5");
  const svg = page.getByTestId("tooth-svg-UR5");
  const before = await svg.boundingBox();
  expect(before).not.toBeNull();
  await label.hover();
  await expect.poll(() => label.evaluate((element) => getComputedStyle(element, "::before").animationName)).not.toBe("none");
  expect(await page.getByTestId("tooth-label-UR4").evaluate((element) => getComputedStyle(element, "::before").animationName)).toBe("none");
  const after = await svg.boundingBox();
  expect(after!.width).toBeCloseTo(before!.width, 1);
  expect(after!.height).toBeCloseTo(before!.height, 1);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect.poll(() => label.evaluate((element) => getComputedStyle(element, "::before").animationName)).toBe("none");
  await label.focus();
  await expect(label).toBeFocused();
  const reduced = await svg.boundingBox();
  expect(reduced!.width).toBeCloseTo(before!.width, 1);
  expect(reduced!.height).toBeCloseTo(before!.height, 1);
});

test("a first-chart age guide never saves or redraws suggested primary teeth before clinical confirmation", async ({ page, request }) => {
  const token = await primePageAuth(page, request);
  const dateOfBirth = `${new Date().getFullYear() - 4}-01-01`;
  const patientId = await createPatient(request, { first_name: "Synthetic", last_name: `First chart age guide ${Date.now()}`, date_of_birth: dateOfBirth });
  const { bodies } = observeWrites(page, patientId);
  await openChart(page, patientId);
  const guide = page.getByTestId("diagnosis-dentition-guide");
  await expect(guide).toBeVisible();
  await expect(guide).toContainText("Unconfirmed age guide");
  await expect(guide).toContainText("Age 4");
  await expect(guide).toContainText("LRA");
  await expect(guide).toContainText("LRE");
  await expect(page.getByTestId("tooth-label-LR1")).toHaveText("LR1");
  await expect(page.getByTestId("tooth-label-LR5")).toHaveText("LR5");
  await expect(page.getByTestId("tooth-svg-LR5")).not.toHaveAttribute("data-dentition", "deciduous");
  expect((await snapshot(request, patientId, token)).teeth).toEqual({});
  expect(bodies).toEqual([]);
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/loading/i);
  await expect(guide).toBeVisible();
  await expect(page.getByTestId("tooth-label-LR5")).toHaveText("LR5");
  expect((await snapshot(request, patientId, token)).teeth).toEqual({});
  expect(bodies).toEqual([]);

  await openMenu(page, "LR5");
  const saved = nextSave(page, patientId);
  await page.getByTestId("clinical-baseline-condition-deciduous").click();
  expect((await saved).ok()).toBeTruthy();
  await expect(guide).toHaveCount(0);
  await expect(page.getByTestId("tooth-label-LR5")).toHaveText("LRE");
  expect(bodies).toEqual([{ teeth: ["LR5"], condition: "deciduous", expected_revisions: { LR5: 0 } }]);
  expect((await snapshot(request, patientId, token)).teeth.LR5).toMatchObject({ condition: "deciduous", revision: 1 });
});

test("synthetic diagnosis palette and selected teeth remain usable in light dark and mobile layouts", async ({ page, request }, testInfo) => {
  const capturePage = async (filename: string) => {
    await page.evaluate(() => {
      window.scrollTo(0, 0);
      return new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
    });
    await page.screenshot({ path: testInfo.outputPath(filename), fullPage: true });
  };
  const { patientId, headers } = await setup(page, request, "Diagnosis preview");
  for (const data of [
    { teeth: ["UR6", "LL6"], condition: "implant", expected_revisions: { UR6: 0, LL6: 0 } },
    { teeth: ["UL3"], movement: "forward", rotation: "clockwise", expected_revisions: { UL3: 0 } },
    { teeth: ["LR5"], condition: "deciduous", expected_revisions: { LR5: 0 } },
  ]) {
    const seeded = await request.post(`${getBaseUrl()}${conditionsPath(patientId)}`, { headers, data });
    expect(seeded.ok()).toBeTruthy();
  }
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.addInitScript(() => localStorage.setItem("dental_pms_theme", "light"));
  await openChart(page, patientId);
  await expect(page.getByTestId("tooth-baseline-implant-UR6")).toBeAttached();
  await expect(page.getByTestId("tooth-baseline-implant-LL6")).toBeAttached();
  await expect(page.getByTestId("tooth-label-LR5")).toHaveText("LRE");
  await chooseTargets(page, "missing", ["UR5", "UR6", "LL6"]);
  const palette = page.getByTestId("clinical-diagnosis-palette");
  const chartBox = await page.getByTestId("clinical-chart").boundingBox();
  const paletteBox = await palette.boundingBox();
  expect(chartBox).not.toBeNull();
  expect(paletteBox).not.toBeNull();
  expect(paletteBox!.y).toBeGreaterThanOrEqual(chartBox!.y + chartBox!.height - 1);
  expect(paletteBox!.width).toBeGreaterThan(paletteBox!.height);
  await expect(page.getByTestId("clinical-chart-midline")).toBeAttached();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
  await capturePage("diagnosis-palette-light.png");
  await page.setViewportSize({ width: 1900, height: 1300 });
  await capturePage("diagnosis-palette-wide-light.png");
  const chartPreviewBox = await page.locator(".patient-route-chart-panel").boundingBox();
  const palettePreviewBox = await palette.boundingBox();
  if (chartPreviewBox && palettePreviewBox) await page.screenshot({
    path: testInfo.outputPath("odontogram-roots-reset-preview.png"),
    fullPage: true,
    clip: { x: chartPreviewBox.x, y: chartPreviewBox.y, width: chartPreviewBox.width, height: palettePreviewBox.y + palettePreviewBox.height - chartPreviewBox.y },
  });
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.getByRole("button", { name: "Toggle theme", exact: true }).click();
  await capturePage("diagnosis-palette-dark.png");
  await page.setViewportSize({ width: 1280, height: 900 });
  await expect(page.getByTestId("diagnosis-apply")).toBeVisible();
  await expectPaletteSizing(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
  await capturePage("diagnosis-palette-1280.png");
  await page.setViewportSize({ width: 390, height: 844 });
  await palette.scrollIntoViewIfNeeded();
  await expect(page.getByTestId("diagnosis-apply")).toBeVisible();
  await expect(page.getByTestId("diagnosis-cancel")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
  const mobileBox = await palette.boundingBox();
  expect(mobileBox!.x).toBeGreaterThanOrEqual(0);
  expect(mobileBox!.x + mobileBox!.width).toBeLessThanOrEqual(391);
  await expectPaletteSizing(page);
  await capturePage("diagnosis-palette-mobile.png");
});
