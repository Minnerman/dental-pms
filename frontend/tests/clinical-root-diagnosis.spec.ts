import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import { addInvoiceLine, createInvoice, createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

const rootChoices = [
  { condition: "filled_sound", label: "Filled sound" },
  { condition: "filled_defective", label: "Filled defective" },
  { condition: "post_core_sound", label: "Post & core sound" },
  { condition: "post_core_defective", label: "Post & core defective" },
] as const;
type RootCondition = typeof rootChoices[number]["condition"];
type RootObservation = { condition: RootCondition | null; apicectomy: boolean };
type RootPatch = Partial<RootObservation>;
type RootMutation = RootPatch & {
  tooth: string;
  root: number;
  dentition: "permanent" | "deciduous";
  expected_revision: number;
};
type Snapshot = {
  patient_id: number;
  teeth: Record<string, {
    condition: string | null;
    revision: number;
    root_observations: Record<string, RootObservation>;
  }>;
  note_teeth: string[];
};

function toothPath(patientId: string) {
  return `/api/patients/${patientId}/clinical/tooth-conditions`;
}

function rootPath(patientId: string) {
  return `/api/patients/${patientId}/clinical/root-conditions`;
}

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

async function recordRoot(request: APIRequestContext, patientId: string, headers: Record<string, string>, data: RootMutation) {
  const response = await request.post(`${getBaseUrl()}${rootPath(patientId)}`, { headers, data });
  expect(response.ok()).toBeTruthy();
  return response.json() as Promise<Snapshot>;
}

async function ready(page: Page) {
  await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/loading|saving/i);
  await expect(page.getByTestId("clinical-diagnosis-palette")).toBeVisible();
}

async function openChart(page: Page, patientId: string) {
  await page.goto(`${getBaseUrl()}/patients/${patientId}/clinical?clinicalView=current`, { waitUntil: "domcontentloaded" });
  await ready(page);
}

async function openRootMenu(page: Page, tooth: string, root: number, button: "left" | "right" = "left") {
  await page.getByTestId(`clinical-root-${tooth}-${root}`).click({ button });
  const menu = page.getByTestId("clinical-root-action-menu");
  await expect(menu).toBeVisible();
  await expect(menu).toHaveAccessibleName(`Root ${root} actions for ${tooth}`);
  return menu;
}

function nextSave(page: Page, path: string) {
  return page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === path);
}

async function chooseRoot(page: Page, patientId: string, tooth: string, root: number, controlId: string) {
  await openRootMenu(page, tooth, root);
  const saved = nextSave(page, rootPath(patientId));
  await page.getByTestId(controlId).click();
  const response = await saved;
  expect(response.ok()).toBeTruthy();
  await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/saving/i);
  return response.request().postDataJSON() as RootMutation;
}

async function rootMenuState(page: Page, tooth: string, root: number, condition: RootCondition | null, apicectomy: boolean) {
  const menu = await openRootMenu(page, tooth, root);
  for (const choice of rootChoices) {
    await expect(menu.getByRole("menuitemradio", { name: choice.label, exact: true })).toHaveAttribute("aria-checked", String(choice.condition === condition));
  }
  await expect(menu.getByRole("menuitemcheckbox", { name: "Apicectomy", exact: true })).toHaveAttribute("aria-checked", String(apicectomy));
  await page.keyboard.press("Escape");
}

async function rootDrawing(page: Page, tooth: string, root: number, condition: RootCondition | null, apicectomy: boolean, recorded: boolean) {
  const target = page.getByTestId(`clinical-root-${tooth}-${root}`);
  await expect(target).toHaveAttribute("data-root-condition", condition ?? "unspecified");
  await expect(target).toHaveAttribute("data-root-recorded", String(recorded));
  await expect(target).toHaveAttribute("data-apicectomy", String(apicectomy));
  await expect(page.getByTestId(`clinical-root-finding-${tooth}-${root}`)).toHaveCount(condition ? 1 : 0);
  await expect(page.getByTestId(`clinical-root-defect-${tooth}-${root}`)).toHaveCount(condition?.endsWith("defective") ? 1 : 0);
  await expect(page.getByTestId(`clinical-root-apicectomy-${tooth}-${root}`)).toHaveCount(apicectomy ? 1 : 0);
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

test("each root condition and apicectomy persist on the chosen molar root without billing", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "Root condition isolation");
  const originalFinance = await readJson(request, `/api/patients/${patientId}/finance-summary`, headers);
  await openChart(page, patientId);
  const writes = observeWrites(page, patientId);
  const originalBox = await page.getByTestId("tooth-svg-UR6").boundingBox();
  expect(originalBox).not.toBeNull();

  let revision = 0;
  for (const choice of rootChoices) {
    const body = await chooseRoot(page, patientId, "UR6", 2, `clinical-root-condition-${choice.condition}`);
    expect(body).toEqual({ tooth: "UR6", root: 2, dentition: "permanent", condition: choice.condition, expected_revision: revision });
    revision += 1;
    const stored = await snapshot(request, patientId, headers);
    expect(Object.keys(stored.teeth)).toEqual(["UR6"]);
    expect(stored.teeth.UR6).toMatchObject({ condition: null, revision, root_observations: { "2": { condition: choice.condition, apicectomy: false } } });
    expect(Object.keys(stored.teeth.UR6.root_observations)).toEqual(["2"]);
    await rootDrawing(page, "UR6", 2, choice.condition, false, true);
    await rootDrawing(page, "UR6", 1, null, false, false);
    await rootDrawing(page, "UR6", 3, null, false, false);
    await rootMenuState(page, "UR6", 2, choice.condition, false);
    const box = await page.getByTestId("tooth-svg-UR6").boundingBox();
    expect(box!.width).toBeCloseTo(originalBox!.width, 1);
    expect(box!.height).toBeCloseTo(originalBox!.height, 1);
  }
  const apicectomy = await chooseRoot(page, patientId, "UR6", 2, "clinical-root-apicectomy");
  expect(apicectomy).toEqual({ tooth: "UR6", root: 2, dentition: "permanent", apicectomy: true, expected_revision: 4 });
  await page.reload({ waitUntil: "domcontentloaded" });
  await ready(page);
  await rootDrawing(page, "UR6", 2, "post_core_defective", true, true);
  await rootMenuState(page, "UR6", 2, "post_core_defective", true);
  await rootMenuState(page, "UR6", 1, null, false);
  await rootMenuState(page, "UR6", 3, null, false);
  await rootMenuState(page, "LR6", 1, null, false);

  const reset = await chooseRoot(page, patientId, "UR6", 2, "clinical-root-reset");
  expect(reset).toEqual({ tooth: "UR6", root: 2, dentition: "permanent", condition: null, apicectomy: false, expected_revision: 5 });
  const stored = await snapshot(request, patientId, headers);
  expect(stored.teeth.UR6).toMatchObject({ condition: null, revision: 6, root_observations: { "2": { condition: null, apicectomy: false } } });
  await rootDrawing(page, "UR6", 2, null, false, true);
  await rootMenuState(page, "UR6", 2, null, false);
  expect(writes.roots).toHaveLength(6);
  expect(writes.teeth).toEqual([]);
  expect(writes.other).toEqual([]);
  expect(await readJson(request, `/api/patients/${patientId}/finance-summary`, headers)).toEqual(originalFinance);
  expect(await readJson(request, `/api/patients/${patientId}/clinical/summary`, headers)).toMatchObject({ recent_procedures: [], treatment_plan_items: [], recent_tooth_notes: [] });
});

test("root left and right menus are separate from whole-tooth tools and respect primary anatomy", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "Root menu boundaries");
  for (const [tooth, condition] of [["UR5", "deciduous"], ["UR7", "missing"], ["UL7", "implant"], ["LL7", "unerupted"]]) {
    const response = await request.post(`${getBaseUrl()}${toothPath(patientId)}`, { headers, data: { teeth: [tooth], condition, expected_revisions: { [tooth]: 0 } } });
    expect(response.ok()).toBeTruthy();
  }
  await openChart(page, patientId);
  const writes = observeWrites(page, patientId);
  await expect(page.getByTestId("tooth-label-UR5")).toHaveText("URE");
  await expect(page.getByTestId("clinical-root-UR6-3")).toBeAttached();
  await expect(page.getByTestId("clinical-root-UR6-4")).toHaveCount(0);
  await expect(page.getByTestId("clinical-root-LR6-2")).toBeAttached();
  await expect(page.getByTestId("clinical-root-LR6-3")).toHaveCount(0);
  for (const tooth of ["UR7", "UL7", "LL7"]) await expect(page.locator(`[data-testid^="clinical-root-${tooth}-"]`)).toHaveCount(0);

  await page.getByTestId("diagnosis-palette-missing").click();
  await page.getByTestId("tooth-label-LL6").click();
  await expect(page.getByTestId("tooth-button-LL6")).toHaveAttribute("data-batch-selected", "true");
  const menu = await openRootMenu(page, "UR6", 1);
  await expect(menu.getByRole("menuitemradio")).toHaveCount(4);
  await expect(page.getByTestId("clinical-tooth-action-menu")).toHaveCount(0);
  await expect(page.getByTestId("clinical-surface-action-menu")).toHaveCount(0);
  await expect(menu.locator('[data-testid^="clinical-baseline-condition-"]')).toHaveCount(0);
  await expect(page.getByTestId("clinical-chart-menu-add-procedure")).toHaveCount(0);
  await expect(page.getByTestId("clinical-chart-menu-add-plan")).toHaveCount(0);
  await expect(page.locator('[data-testid^="tooth-button-"][data-batch-selected="true"]')).toHaveCount(0);
  await expect(page.getByTestId("diagnosis-apply")).toBeDisabled();
  await page.keyboard.press("Escape");
  await openRootMenu(page, "UR6", 3, "right");
  await page.keyboard.press("Escape");
  await page.getByTestId("clinical-root-UR6-1").focus();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("clinical-root-action-menu")).toHaveAccessibleName("Root 1 actions for UR6");
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("clinical-root-UR6-1")).toBeFocused();
  await page.keyboard.press("Shift+F10");
  await expect(page.getByTestId("clinical-root-action-menu")).toHaveAccessibleName("Root 1 actions for UR6");
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("clinical-root-UR6-1")).toBeFocused();
  await page.getByTestId("tooth-label-UR6").click({ button: "right" });
  await expect(page.getByTestId("clinical-tooth-action-menu")).toBeVisible();
  await expect(page.getByTestId("clinical-root-condition-filled_sound")).toHaveCount(0);
  await page.keyboard.press("Escape");
  expect(writes.roots).toEqual([]);
  expect(writes.teeth).toEqual([]);

  await openRootMenu(page, "UR5", 3, "right");
  await expect(page.getByTestId("clinical-root-action-menu")).toContainText("URE · Root 3");
  const saved = nextSave(page, rootPath(patientId));
  await page.getByTestId("clinical-root-condition-filled_sound").click();
  const response = await saved;
  expect(response.ok()).toBeTruthy();
  expect(response.request().postDataJSON()).toEqual({ tooth: "UR5", root: 3, dentition: "deciduous", condition: "filled_sound", expected_revision: 1 });
  expect((await snapshot(request, patientId, headers)).teeth.UR5).toMatchObject({ condition: "deciduous", revision: 2, root_observations: { "3": { condition: "filled_sound", apicectomy: false } } });
  await rootDrawing(page, "UR5", 3, "filled_sound", false, true);
  expect(writes.other).toEqual([]);
});

test("whole-tooth Reset clears its root observations but preserves other roots notes history and finance", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "Root reset retention");
  await recordRoot(request, patientId, headers, { tooth: "UR6", root: 1, dentition: "permanent", condition: "filled_sound", apicectomy: true, expected_revision: 0 });
  await recordRoot(request, patientId, headers, { tooth: "UR6", root: 2, dentition: "permanent", condition: "post_core_defective", expected_revision: 1 });
  await recordRoot(request, patientId, headers, { tooth: "LR6", root: 1, dentition: "permanent", condition: "filled_defective", expected_revision: 0 });
  const note = await request.post(`${getBaseUrl()}/api/patients/${patientId}/tooth-notes`, { headers, data: { tooth: "UR6", surface: null, note: "Synthetic root history must remain after chart reset" } });
  expect(note.ok()).toBeTruthy();
  const procedure = await request.post(`${getBaseUrl()}/api/patients/${patientId}/procedures`, { headers, data: { tooth: "UR6", procedure_code: "ROOT_HISTORY_PROOF", description: "Synthetic previously completed treatment", fee_pence: 12500 } });
  expect(procedure.ok()).toBeTruthy();
  const invoice = await createInvoice(request, patientId, { notes: "Synthetic root history invoice" });
  await addInvoiceLine(request, invoice.id, { description: "Synthetic earlier charge", quantity: 1, unit_price_pence: 12500 });
  const paths = [`/api/patients/${patientId}/tooth-history?tooth=UR6`, `/api/patients/${patientId}/finance-summary`, `/api/invoices/${invoice.id}`];
  const before = await Promise.all(paths.map((path) => readJson(request, path, headers)));
  await openChart(page, patientId);
  const writes = observeWrites(page, patientId);
  await expect(page.getByTestId("tooth-note-flag-UR6")).toBeVisible();
  await page.getByTestId("tooth-label-UR6").click({ button: "right" });
  const saved = nextSave(page, toothPath(patientId));
  await page.getByTestId("clinical-baseline-condition-reset").click();
  const response = await saved;
  expect(response.ok()).toBeTruthy();
  expect(response.request().postDataJSON()).toEqual({ teeth: ["UR6"], condition: "unrecorded", movement: null, rotation: null, expected_revisions: { UR6: 2 } });
  await expect(page.getByTestId("tooth-svg-UR6")).toHaveAttribute("data-baseline-status", "unrecorded");
  await page.reload({ waitUntil: "domcontentloaded" });
  await ready(page);
  const stored = await snapshot(request, patientId, headers);
  expect(stored.teeth.UR6).toMatchObject({ condition: "unrecorded", revision: 3, root_observations: {} });
  expect(stored.teeth.LR6).toMatchObject({ revision: 1, root_observations: { "1": { condition: "filled_defective", apicectomy: false } } });
  await rootDrawing(page, "UR6", 1, null, false, false);
  await rootDrawing(page, "UR6", 2, null, false, false);
  await rootDrawing(page, "LR6", 1, "filled_defective", false, true);
  await rootMenuState(page, "UR6", 1, null, false);
  await rootMenuState(page, "UR6", 2, null, false);
  await rootMenuState(page, "LR6", 1, "filled_defective", false);
  await expect(page.getByTestId("tooth-note-flag-UR6")).toBeVisible();
  expect(await Promise.all(paths.map((path) => readJson(request, path, headers)))).toEqual(before);
  expect(writes.roots).toEqual([]);
  expect(writes.teeth).toHaveLength(1);
  expect(writes.other).toEqual([]);
});

test("a native root finding overrides historical absence badges only in Current", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "Root historical badge precedence");
  await recordRoot(request, patientId, headers, { tooth: "UR6", root: 2, dentition: "permanent", condition: "filled_sound", expected_revision: 0 });
  const history = await request.post(`${getBaseUrl()}/api/patients/${patientId}/procedures`, { headers, data: { tooth: "UR6", procedure_code: "ROOT_HISTORY_BADGE", description: "Synthetic earlier treatment retained in History", fee_pence: 0 } });
  expect(history.ok()).toBeTruthy();
  // This is a synthetic import-shaped response, never a connection to R4.
  const historical = {
    patient_id: Number(patientId), legacy_patient_code: null,
    teeth: { "16": { missing: true, extracted: true, restorations: [
      { type: "implant", surfaces: [], meta: { source: "synthetic-test", code_label: "Synthetic historical implant" } },
      { type: "extraction", surfaces: [], meta: { source: "synthetic-test", code_label: "Synthetic historical extraction" } },
    ] } },
  };
  await page.route(`**/api/patients/${patientId}/charting/tooth-state*`, (route) => route.fulfill({ json: historical }));
  await openChart(page, patientId);
  const writes = observeWrites(page, patientId);
  const expectCurrent = async () => {
    await rootDrawing(page, "UR6", 2, "filled_sound", false, true);
    await expect(page.getByTestId("tooth-root-UR6-1")).toBeAttached();
    await expect(page.getByTestId("tooth-root-UR6-3")).toBeAttached();
    await expect(page.getByTestId("tooth-svg-UR6")).not.toHaveAttribute("data-baseline-status", "present");
    for (const mark of ["missing", "extracted", "implant", "extraction"]) {
      await expect(page.getByTestId(`tooth-restoration-UR6-${mark}`)).toHaveCount(0);
    }
    await expect(page.getByTestId("tooth-anatomy-restoration-UR6-implant")).toHaveCount(0);
    await expect(page.getByTestId("tooth-badge-UR6").locator('[title="Missing tooth"], [title="Extracted tooth"]')).toHaveCount(0);
    await expect(page.getByTestId("tooth-badge-UR6").locator('[title="History"]')).toHaveText("H");
  };
  await expectCurrent();
  await page.getByTestId("clinical-chart-view-history").click();
  await expect(page.getByTestId("clinical-root-finding-UR6-2")).toHaveCount(0);
  for (const mark of ["missing", "extracted", "implant", "extraction"]) {
    await expect(page.getByTestId(`tooth-restoration-UR6-${mark}`)).toBeAttached();
  }
  await expect(page.getByTestId("tooth-anatomy-restoration-UR6-implant")).toBeAttached();
  await expect(page.getByTestId("tooth-badge-UR6").locator('[title="Missing tooth"]')).toHaveText("M");
  await expect(page.getByTestId("tooth-badge-UR6").locator('[title="Extracted tooth"]')).toHaveText("X");
  await expect(page.getByTestId("tooth-badge-UR6").locator('[title="History"]')).toHaveText("H");
  await page.getByTestId("clinical-chart-view-current").click();
  await expectCurrent();
  expect((await snapshot(request, patientId, headers)).teeth.UR6).toMatchObject({ condition: null, revision: 1, root_observations: { "2": { condition: "filled_sound", apicectomy: false } } });
  expect(writes.roots).toEqual([]);
  expect(writes.teeth).toEqual([]);
  expect(writes.other).toEqual([]);
});

test("root diagnosis stays read-only for viewers and is unavailable in Planned or History", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "Root permission boundaries");
  await recordRoot(request, patientId, headers, { tooth: "UR6", root: 1, dentition: "permanent", condition: "filled_sound", expected_revision: 0 });
  await openChart(page, patientId);
  const writes = observeWrites(page, patientId);
  for (const mode of ["planned", "history"]) {
    await page.getByTestId(`clinical-chart-view-${mode}`).click();
    await expect(page.getByTestId(`clinical-chart-view-${mode}`)).toHaveAttribute("aria-pressed", "true");
    const inactiveRoot = page.getByTestId("clinical-root-UR6-1");
    await expect(inactiveRoot).not.toHaveAttribute("role", "button");
    await inactiveRoot.scrollIntoViewIfNeeded();
    const bounds = await inactiveRoot.boundingBox();
    expect(bounds).not.toBeNull();
    await page.mouse.click(bounds!.x + bounds!.width / 2, bounds!.y + bounds!.height / 2, { button: "right" });
    await expect(page.getByTestId("clinical-root-action-menu")).toHaveCount(0);
    await expect(page.getByTestId("clinical-root-condition-filled_sound")).toHaveCount(0);
    await page.keyboard.press("Escape");
  }
  await page.route("**/api/me/capabilities", (route) => route.fulfill({ json: ["patients.view", "clinical.view"] }));
  await openChart(page, patientId);
  await expect(page.getByTestId("patient-clinical-section")).toHaveAttribute("data-clinical-mode", "read-only");
  const menu = await openRootMenu(page, "UR6", 1);
  for (const choice of rootChoices) await expect(menu.getByRole("menuitemradio", { name: choice.label, exact: true })).toBeDisabled();
  await expect(menu.getByRole("menuitemradio", { name: "Filled sound", exact: true })).toHaveAttribute("aria-checked", "true");
  await expect(menu.getByTestId("clinical-root-apicectomy")).toBeDisabled();
  await expect(menu.getByTestId("clinical-root-reset")).toBeDisabled();
  expect(writes.roots).toEqual([]);
  expect(writes.teeth).toEqual([]);
  expect((await snapshot(request, patientId, headers)).teeth.UR6.revision).toBe(1);
});

test("root edits and whole-tooth resets reject each other's stale revision", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "Root stale revision");
  await openChart(page, patientId);
  // A second synthetic operator resets the same tooth after the browser's read.
  const reset = await request.post(`${getBaseUrl()}${toothPath(patientId)}`, { headers, data: { teeth: ["UR6"], condition: "unrecorded", movement: null, rotation: null, expected_revisions: { UR6: 0 } } });
  expect(reset.ok()).toBeTruthy();
  await openRootMenu(page, "UR6", 2);
  const rootConflict = nextSave(page, rootPath(patientId));
  await page.getByTestId("clinical-root-condition-filled_sound").click();
  expect((await rootConflict).status()).toBe(409);
  await expect(page.getByTestId("clinical-baseline-error")).toContainText(/changed.*Refresh/i);
  expect((await snapshot(request, patientId, headers)).teeth.UR6).toMatchObject({ condition: "unrecorded", revision: 1, root_observations: {} });
  await page.getByRole("button", { name: "Refresh conditions", exact: true }).click();
  await expect(page.getByTestId("clinical-baseline-error")).toHaveCount(0);
  await expect(page.getByTestId("tooth-svg-UR6")).toHaveAttribute("data-baseline-status", "unrecorded");

  await recordRoot(request, patientId, headers, { tooth: "UR6", root: 2, dentition: "permanent", condition: "filled_defective", apicectomy: true, expected_revision: 1 });
  await page.getByTestId("tooth-label-UR6").click({ button: "right" });
  const toothConflict = nextSave(page, toothPath(patientId));
  await page.getByTestId("clinical-baseline-condition-reset").click();
  expect((await toothConflict).status()).toBe(409);
  await expect(page.getByTestId("clinical-baseline-error")).toContainText(/changed.*Refresh/i);
  expect((await snapshot(request, patientId, headers)).teeth.UR6).toMatchObject({ condition: "unrecorded", revision: 2, root_observations: { "2": { condition: "filled_defective", apicectomy: true } } });
  await page.getByRole("button", { name: "Refresh conditions", exact: true }).click();
  await expect(page.getByTestId("clinical-baseline-error")).toHaveCount(0);
  await ready(page);
  await rootDrawing(page, "UR6", 2, "filled_defective", true, true);
  await rootMenuState(page, "UR6", 2, "filled_defective", true);
});

test("a pending or failed root save cannot duplicate mutate another tooth or claim success", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "Root failure safety");
  await openChart(page, patientId);
  const writes = observeWrites(page, patientId);
  let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route(`**${rootPath(patientId)}`, async (route) => {
    await gate;
    await route.fulfill({ status: 500, contentType: "text/html", body: "<html>synthetic private infrastructure diagnostic</html>" });
  });
  const response = nextSave(page, rootPath(patientId));
  try {
    await openRootMenu(page, "UR6", 1);
    await page.getByTestId("clinical-root-condition-post_core_sound").click();
    await expect(page.getByTestId("clinical-baseline-status")).toContainText(/saving/i);
    await expect(page.getByTestId("diagnosis-palette-missing")).toBeDisabled();
    await expect(page.getByTestId("diagnosis-apply")).toBeDisabled();
    const menu = await openRootMenu(page, "UR6", 2);
    for (const choice of rootChoices) await expect(menu.getByRole("menuitemradio", { name: choice.label, exact: true })).toBeDisabled();
    await page.keyboard.press("Escape");
    await page.getByTestId("tooth-label-LR6").click({ button: "right" });
    await expect(page.getByTestId("clinical-baseline-condition-reset")).toBeDisabled();
    await page.keyboard.press("Escape");
    expect(writes.roots).toHaveLength(1);
    expect(writes.teeth).toEqual([]);
    await rootDrawing(page, "UR6", 1, null, false, false);
    expect((await snapshot(request, patientId, headers)).teeth).toEqual({});
  } finally {
    release();
  }
  expect((await response).status()).toBe(500);
  await expect(page.getByTestId("clinical-baseline-error")).toContainText(/could not be confirmed/i);
  await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/saved/i);
  await expect(page.getByText("synthetic private infrastructure diagnostic")).toHaveCount(0);
  expect((await snapshot(request, patientId, headers)).teeth).toEqual({});
  await rootDrawing(page, "UR6", 1, null, false, false);
  await page.unroute(`**${rootPath(patientId)}`);
  await page.getByRole("button", { name: "Refresh conditions", exact: true }).click();
  await expect(page.getByTestId("clinical-baseline-error")).toHaveCount(0);
  await ready(page);
  const retried = await chooseRoot(page, patientId, "UR6", 1, "clinical-root-condition-post_core_sound");
  expect(retried.expected_revision).toBe(0);
  expect((await snapshot(request, patientId, headers)).teeth.UR6).toMatchObject({ revision: 1, root_observations: { "1": { condition: "post_core_sound", apicectomy: false } } });
  expect(writes.roots).toHaveLength(2);
  expect(writes.teeth).toEqual([]);
  expect(writes.other).toEqual([]);
});

test("synthetic root findings and their menu stay legible in light dark and compact layouts", async ({ page, request }, testInfo) => {
  const { patientId, headers } = await setup(page, request, "Root visual preview");
  const fixtures: RootMutation[] = [
    { tooth: "UR6", root: 1, dentition: "permanent", condition: "filled_sound", expected_revision: 0 },
    { tooth: "UR6", root: 2, dentition: "permanent", condition: "filled_defective", apicectomy: true, expected_revision: 1 },
    { tooth: "UR6", root: 3, dentition: "permanent", condition: "post_core_sound", expected_revision: 2 },
    { tooth: "UL6", root: 2, dentition: "permanent", condition: "post_core_defective", expected_revision: 0 },
    { tooth: "LR6", root: 1, dentition: "permanent", condition: "post_core_sound", apicectomy: true, expected_revision: 0 },
    { tooth: "LL6", root: 2, dentition: "permanent", condition: "filled_defective", expected_revision: 0 },
  ];
  for (const data of fixtures) await recordRoot(request, patientId, headers, data);
  await openChart(page, patientId);
  const writes = observeWrites(page, patientId);
  for (const fixture of fixtures) await rootDrawing(page, fixture.tooth, fixture.root, fixture.condition ?? null, fixture.apicectomy ?? false, true);
  await page.emulateMedia({ reducedMotion: "no-preference" });
  const target = page.getByTestId("clinical-root-UR6-1");
  await target.hover();
  await expect(target.locator(".clinical-root-halo")).not.toHaveCSS("animation-name", "none");
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(target.locator(".clinical-root-halo")).toHaveCSS("animation-name", "none");
  await page.getByTestId("clinical-chart-view-current").hover();
  const capture = async (name: string) => {
    await page.evaluate(() => { window.scrollTo(0, 0); return new Promise<void>((resolve) => requestAnimationFrame(() => resolve())); });
    const path = testInfo.outputPath(`${name}.png`);
    await page.screenshot({ path, fullPage: true });
    await testInfo.attach(name, { path, contentType: "image/png" });
  };
  const expectMenuStyling = async () => {
    const menu = page.getByTestId("clinical-root-action-menu");
    const selected = menu.getByTestId("clinical-root-condition-filled_defective");
    const unselected = menu.getByTestId("clinical-root-condition-filled_sound");
    for (const choice of rootChoices) await expect(menu.getByTestId(`clinical-root-condition-${choice.condition}`)).toHaveCSS("gap", "10px");
    for (const control of [selected, menu.getByTestId("clinical-root-apicectomy")]) {
      await expect(control).toHaveAttribute("aria-checked", "true");
      await expect(control).toHaveCSS("border-left-color", "rgb(11, 158, 192)");
      await expect(control).toHaveCSS("background-color", "rgba(11, 158, 192, 0.13)");
      await expect(control).toHaveCSS("box-shadow", /inset/);
    }
    await expect(unselected).toHaveAttribute("aria-checked", "false");
    expect(await unselected.evaluate((element) => getComputedStyle(element).backgroundColor))
      .not.toBe(await selected.evaluate((element) => getComputedStyle(element).backgroundColor));
  };
  const captureChart = async (name: string, includeMenu: boolean) => {
    const bounds = await page.getByTestId("clinical-chart").boundingBox();
    expect(bounds).not.toBeNull();
    const menu = includeMenu ? await page.getByTestId("clinical-root-action-menu").boundingBox() : null;
    const x = Math.max(0, Math.min(bounds!.x, menu?.x ?? bounds!.x) - 10);
    const y = Math.max(0, Math.min(bounds!.y, menu?.y ?? bounds!.y) - 10);
    const right = Math.max(bounds!.x + bounds!.width, menu ? menu.x + menu.width : 0) + 10;
    const bottom = Math.max(bounds!.y + bounds!.height, menu ? menu.y + menu.height : 0) + 10;
    expect(right).toBeLessThanOrEqual(1900);
    expect(bottom).toBeLessThanOrEqual(1400);
    const path = testInfo.outputPath(`${name}.png`);
    await page.screenshot({ path, clip: { x, y, width: right - x, height: bottom - y } });
    await testInfo.attach(name, { path, contentType: "image/png" });
  };
  await capture("root-diagnosis-light");
  await page.getByRole("button", { name: "Toggle theme", exact: true }).click();
  await capture("root-diagnosis-dark");
  await openRootMenu(page, "UR6", 2, "right");
  await expectMenuStyling();
  const menuPath = testInfo.outputPath("root-diagnosis-dark-menu.png");
  await page.screenshot({ path: menuPath });
  await testInfo.attach("root-diagnosis-dark-menu", { path: menuPath, contentType: "image/png" });
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Toggle theme", exact: true }).click();
  await page.setViewportSize({ width: 1900, height: 1100 });
  await capture("root-diagnosis-wide");
  await page.setViewportSize({ width: 1900, height: 1400 });
  await page.evaluate(() => { window.scrollTo(0, 0); return new Promise<void>((resolve) => requestAnimationFrame(() => resolve())); });
  await captureChart("root-diagnosis-chart-closeup", false);
  await openRootMenu(page, "UR6", 2, "right");
  await expectMenuStyling();
  await captureChart("root-diagnosis-chart-menu-closeup", true);
  await page.keyboard.press("Escape");
  await page.setViewportSize({ width: 390, height: 844 });
  const menu = await openRootMenu(page, "UR6", 2);
  const bounds = await menu.boundingBox();
  expect(bounds).not.toBeNull();
  expect(bounds!.x).toBeGreaterThanOrEqual(0);
  expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(390);
  expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(844);
  await expect(menu.getByTestId("clinical-root-reset")).toBeVisible();
  const mobilePath = testInfo.outputPath("root-diagnosis-mobile-menu.png");
  await page.screenshot({ path: mobilePath });
  await testInfo.attach("root-diagnosis-mobile-menu", { path: mobilePath, contentType: "image/png" });
  await page.keyboard.press("Escape");
  await capture("root-diagnosis-mobile");
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(391);
  expect(writes.roots).toEqual([]);
  expect(writes.teeth).toEqual([]);
  expect(writes.other).toEqual([]);
});
