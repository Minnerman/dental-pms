import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";
import type { PlanningDrawingKind, PlanningItem, PlanningSnapshot, PlanningTarget } from "../components/clinical/treatmentPlanning";

type Item = PlanningItem & { material: string | null };
type Fixture = { id: string; headers: Record<string, string>; endpoint: string };
type Catalogue = { id: number; name: string };

async function fixture(page: Page, request: APIRequestContext): Promise<Fixture> {
  const token = await primePageAuth(page, request);
  const id = await createPatient(request, { first_name: "Synthetic", last_name: `Completed chart ${Date.now()}` });
  await page.setViewportSize({ width: 1900, height: 1200 });
  return { id, headers: { Authorization: `Bearer ${token}` }, endpoint: `${getBaseUrl()}/api/patients/${id}` };
}
async function native(request: APIRequestContext, value: Fixture): Promise<PlanningSnapshot["native"]> {
  const response = await request.get(`${value.endpoint}/clinical/tooth-conditions`, { headers: value.headers });
  expect(response.ok()).toBeTruthy(); return response.json();
}
async function record(request: APIRequestContext, value: Fixture, route: string, data: unknown) {
  const response = await request.post(`${value.endpoint}/clinical/${route}`, { headers: value.headers, data });
  expect(response.ok()).toBeTruthy(); return response.json();
}
async function catalogue(request: APIRequestContext, value: Fixture, level: PlanningTarget["level"], suffix: string): Promise<Catalogue> {
  const name = `Synthetic effect ${suffix} ${value.id}`;
  const response = await request.post(`${getBaseUrl()}/api/treatments`, { headers: value.headers, data: { name, code: `EFFECT-${value.id}-${suffix}`, level, is_active: true } });
  expect(response.ok()).toBeTruthy(); const item = await response.json();
  const fee = await request.put(`${getBaseUrl()}/api/treatments/${item.id}/fees`, { headers: value.headers, data: [{ patient_category: "CLINIC_PRIVATE", fee_type: "FIXED", amount_pence: 1500 }] });
  expect(fee.ok()).toBeTruthy(); return { id: item.id, name };
}
async function start(page: Page, request: APIRequestContext, value: Fixture) {
  await page.goto(`${getBaseUrl()}/patients/${value.id}/clinical?clinicalView=planned`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("planning-start")).toBeVisible({ timeout: 30_000 }); await page.getByTestId("planning-start").click();
  await expect(page.getByTestId("treatment-planning-chart")).toBeVisible();
  const response = await request.get(`${value.endpoint}/planning`, { headers: value.headers }); expect(response.ok()).toBeTruthy();
  return (await response.json()).plan.snapshot as PlanningSnapshot;
}
async function add(page: Page, value: Fixture, treatment: Catalogue, target: PlanningTarget, drawing: PlanningDrawingKind, material?: string): Promise<Item> {
  await page.getByTestId(`planning-level-${target.level}`).click();
  const targetId = target.level === "surface" ? `clinical-surface-${target.tooth}-${target.surfaces[0]}`
    : target.level === "crown" ? `clinical-crown-${target.tooth}` : `planning-tooth-number-${target.tooth}`;
  await page.getByTestId(targetId).click(); await expect(page.getByTestId("planning-treatment-dialog")).toBeVisible();
  await page.getByTestId("planning-catalogue-search").fill(treatment.name); await page.getByTestId(`planning-catalogue-item-${treatment.id}`).click();
  await page.getByTestId("planning-drawing-kind").selectOption(drawing);
  if (material !== undefined) {
    await expect(page.getByTestId("planning-material")).toHaveValue("");
    await page.getByTestId("planning-material").selectOption(material);
  }
  if (target.level === "surface") for (const surface of target.surfaces) await page.getByTestId(`planning-target-surface-${surface}`).check();
  const saved = page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === `/api/patients/${value.id}/planning/items`);
  await page.getByTestId("planning-save").click(); const response = await saved; expect(response.ok()).toBeTruthy();
  expect(response.request().postDataJSON()).toMatchObject({ target, drawing_kind: drawing, ...(material !== undefined ? { material } : {}) });
  const item = await response.json() as Item;
  await expect(page.getByTestId("planning-treatment-dialog")).toBeHidden(); await expect(page.getByTestId(`planning-item-${item.id}`)).toHaveAttribute("data-status", "proposed");
  return item;
}
async function complete(page: Page, value: Fixture, item: Item): Promise<Item> {
  await page.getByTestId(`planning-item-${item.id}`).click();
  const saved = page.waitForResponse((response) => response.request().method() === "PATCH" && new URL(response.url()).pathname === `/api/patients/${value.id}/planning/items/${item.id}`);
  page.once("dialog", (dialog) => dialog.accept()); await page.getByTestId("planning-action-complete").click();
  const response = await saved; expect(response.ok()).toBeTruthy(); expect(response.request().postDataJSON()).toMatchObject({ status: "completed", confirm_finance: true });
  await expect(page.getByTestId(`planning-item-${item.id}`)).toHaveAttribute("data-status", "completed");
  const result = await response.json() as Item; expect(result.completed_procedure_id).toBeTruthy(); return result;
}
async function undo(page: Page, value: Fixture, item: Item) {
  await page.getByTestId(`planning-item-${item.id}`).click(); await page.getByTestId("planning-action-uncomplete").click();
  await expect(page.getByTestId("planning-uncomplete-confirm")).toBeDisabled();
  await page.getByTestId("planning-uncomplete-reason").fill("Synthetic completion correction; treatment remains outstanding");
  const saved = page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === `/api/patients/${value.id}/planning/items/${item.id}/uncomplete`);
  await page.getByTestId("planning-uncomplete-confirm").click(); const response = await saved; expect(response.ok()).toBeTruthy();
  expect(await response.json()).toMatchObject({ id: item.id, status: "proposed", completed_procedure_id: null });
  await expect(page.getByTestId("planning-uncomplete-dialog")).toBeHidden(); await expect(page.getByTestId(`planning-item-${item.id}`)).toHaveAttribute("data-status", "proposed");
}
async function unchanged(request: APIRequestContext, value: Fixture, original: PlanningSnapshot["native"], captured: PlanningSnapshot) {
  expect((await native(request, value)).teeth).toEqual(original.teeth);
  const response = await request.get(`${value.endpoint}/planning`, { headers: value.headers }); expect(response.ok()).toBeTruthy();
  expect((await response.json()).plan.snapshot).toEqual(captured);
}
async function reload(page: Page) {
  await page.reload({ waitUntil: "domcontentloaded" }); await expect(page.getByTestId("treatment-planning-chart")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("planning-loading")).toHaveCount(0);
}
async function view(page: Page, mode: "current" | "planned") {
  await page.getByTestId(`clinical-chart-view-${mode}`).click();
  await expect(page.getByTestId(mode === "current" ? "clinical-chart" : "treatment-planning-chart")).toBeVisible({ timeout: 30_000 });
  if (mode === "current") await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/loading|saving/i, { timeout: 30_000 });
  else await expect(page.getByTestId("planning-loading")).toHaveCount(0);
}

test("real extraction completion removes the planned tooth and undo restores its captured appearance without diagnosis writes", async ({ page, request }) => {
  const value = await fixture(page, request), treatment = await catalogue(request, value, "tooth", "extraction");
  const original = await native(request, value), captured = await start(page, request, value);
  const crown = page.getByTestId("tooth-crown-UR6"), chart = page.getByTestId("treatment-planning-chart");
  await expect(crown).toBeAttached(); const originalPath = await crown.getAttribute("d");
  const item = await add(page, value, treatment, { level: "tooth", tooth: "UR6", surfaces: [] }, "extraction");
  await expect(crown).toBeAttached(); await expect(chart.getByTestId("tooth-svg-UR6")).not.toHaveAttribute("data-baseline-status", "missing");
  const completed = await complete(page, value, item);
  await expect(chart.getByTestId("tooth-svg-UR6")).toHaveAttribute("data-baseline-status", "missing"); await expect(crown).toHaveCount(0);
  await expect(page.getByTestId("planning-tooth-UR6")).toHaveAttribute("data-projected-completion-ids", String(completed.completed_procedure_id));
  await view(page, "current"); await expect(page.getByTestId("tooth-svg-UR6")).toHaveAttribute("data-baseline-status", "missing"); await expect(crown).toHaveCount(0);
  await view(page, "planned");
  await reload(page); await expect(crown).toHaveCount(0); await unchanged(request, value, original, captured);
  await undo(page, value, completed); await expect(crown).toHaveAttribute("d", originalPath!);
  await expect(page.getByTestId(`tooth-planning-overlay-UR6-${item.id}`)).toHaveAttribute("data-plan-status", "planned");
  await reload(page); await expect(crown).toHaveAttribute("d", originalPath!); await unchanged(request, value, original, captured);
  await view(page, "current"); await expect(crown).toHaveAttribute("d", originalPath!); await expect(page.getByTestId("tooth-svg-UR6")).not.toHaveAttribute("data-baseline-status", "missing");
  const ledger = await request.get(`${value.endpoint}/ledger`, { headers: value.headers }); expect(ledger.ok()).toBeTruthy();
  const entries = (await ledger.json()).filter((entry: { reference: string | null }) => entry.reference?.startsWith(`TREATMENT-PLAN:${item.id}`)) as { amount_pence: number }[];
  expect(entries).toHaveLength(2); expect(entries.reduce((sum, entry) => sum + entry.amount_pence, 0)).toBe(0);
});

test("real implant completion replaces a captured missing slot and undo restores the slot after reload", async ({ page, request }) => {
  const value = await fixture(page, request); await record(request, value, "tooth-conditions", { teeth: ["LR5"], condition: "missing", expected_revisions: { LR5: 0 } });
  const treatment = await catalogue(request, value, "tooth", "implant"), original = await native(request, value), captured = await start(page, request, value);
  const tooth = page.getByTestId("tooth-svg-LR5"), implant = page.getByTestId("tooth-baseline-implant-LR5");
  await expect(tooth).toHaveAttribute("data-baseline-status", "missing"); await expect(implant).toHaveCount(0);
  const item = await add(page, value, treatment, { level: "tooth", tooth: "LR5", surfaces: [] }, "implant");
  await expect(tooth).toHaveAttribute("data-baseline-status", "missing");
  const completed = await complete(page, value, item); await expect(tooth).toHaveAttribute("data-baseline-status", "implant"); await expect(implant).toBeAttached();
  await view(page, "current"); await expect(tooth).toHaveAttribute("data-baseline-status", "implant"); await expect(implant).toBeAttached(); await view(page, "planned");
  await reload(page); await expect(implant).toBeAttached(); await unchanged(request, value, original, captured);
  await undo(page, value, completed); await expect(tooth).toHaveAttribute("data-baseline-status", "missing"); await expect(implant).toHaveCount(0);
  await reload(page); await expect(tooth).toHaveAttribute("data-baseline-status", "missing"); await expect(implant).toHaveCount(0); await unchanged(request, value, original, captured);
  await view(page, "current"); await expect(tooth).toHaveAttribute("data-baseline-status", "missing"); await expect(implant).toHaveCount(0);
});

test("real completed crown and MOD filling use explicit diagnosis materials and material edits preserve the saved fee", async ({ page, request }) => {
  const value = await fixture(page, request);
  await record(request, value, "crown-conditions", { teeth: ["UL6"], kind: "porcelain_bonded", issues: [], expected_revisions: { UL6: 0 } });
  await record(request, value, "surface-conditions", { targets: [{ tooth: "LL6", surfaces: ["M"] }], observation: { kind: "restored", material: "gold", condition: "sound", defects: [] }, expected_revisions: { LL6: 0 } });
  await record(request, value, "surface-conditions", { targets: [{ tooth: "LR6", surfaces: ["M"] }], observation: { kind: "carious", material: null, condition: "carious_established", defects: [] }, expected_revisions: { LR6: 0 } });
  await page.goto(`${getBaseUrl()}/patients/${value.id}/clinical?clinicalView=current`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("clinical-crown-UL6")).toHaveAttribute("data-crown-kind", "porcelain_bonded");
  const crownFill = await page.getByTestId("tooth-crown-UL6").getAttribute("fill"), surfaceFill = await page.getByTestId("clinical-surface-fill-LL6-M").getAttribute("fill");
  expect(crownFill).toBeTruthy(); expect(surfaceFill).toBeTruthy();
  const crownTreatment = await catalogue(request, value, "crown", "crown"), fillingTreatment = await catalogue(request, value, "surface", "filling");
  const original = await native(request, value), captured = await start(page, request, value);
  const crownItem = await add(page, value, crownTreatment, { level: "crown", tooth: "UR6", surfaces: [] }, "crown", "gold");
  await expect(page.getByTestId("clinical-crown-UR6")).toHaveAttribute("data-crown-kind", "untouched");
  await page.getByTestId(`planning-item-${crownItem.id}`).click(); await page.getByTestId("planning-action-material").click();
  await expect(page.getByTestId("planning-material-dialog")).toBeVisible(); await expect(page.getByTestId("planning-edit-material")).toHaveValue("gold");
  await page.getByTestId("planning-edit-material").selectOption("porcelain_bonded");
  const changed = page.waitForResponse((response) => response.request().method() === "PATCH" && new URL(response.url()).pathname === `/api/patients/${value.id}/planning/items/${crownItem.id}`);
  await page.getByTestId("planning-material-save").click(); const changedResponse = await changed; expect(changedResponse.ok()).toBeTruthy();
  expect(changedResponse.request().postDataJSON()).toEqual({ expected_revision: crownItem.revision, material: "porcelain_bonded" });
  const changedItem = await changedResponse.json() as Item; expect(changedItem).toMatchObject({ fee_pence: crownItem.fee_pence, fee_mode: crownItem.fee_mode, target: crownItem.target, material: "porcelain_bonded" });
  await expect(page.getByTestId("planning-material-dialog")).toBeHidden();
  const fillingItem = await add(page, value, fillingTreatment, { level: "surface", tooth: "LR6", surfaces: ["M", "O", "D"] }, "filling", "gold");
  await expect(page.getByTestId("clinical-surface-LR6-M")).toHaveAttribute("data-surface-kind", "carious");
  const completedCrown = await complete(page, value, changedItem); await expect(page.getByTestId("planning-action-material")).toBeDisabled();
  const completedFilling = await complete(page, value, fillingItem);
  await expect(page.getByTestId("clinical-crown-UR6")).toHaveAttribute("data-crown-kind", "porcelain_bonded"); await expect(page.getByTestId("tooth-crown-UR6")).toHaveAttribute("fill", crownFill!);
  for (const surface of ["M", "O", "D"]) {
    await expect(page.getByTestId(`clinical-surface-LR6-${surface}`)).toHaveAttribute("data-surface-material", "gold");
    await expect(page.getByTestId(`clinical-surface-LR6-${surface}`)).toHaveAttribute("data-surface-condition", "sound");
    await expect(page.getByTestId(`clinical-surface-fill-LR6-${surface}`)).toHaveAttribute("fill", surfaceFill!);
  }
  await expect(page.getByTestId("clinical-surface-LR6-B")).toHaveAttribute("data-surface-kind", "untouched");
  await expect(page.getByTestId("clinical-surface-pattern-LR6-M")).toHaveCount(0); await unchanged(request, value, original, captured);
  const previews = path.join(process.cwd(), ".run", "planning-completion-previews"); await mkdir(previews, { recursive: true });
  await view(page, "current");
  await expect(page.getByTestId("clinical-crown-UR6")).toHaveAttribute("data-crown-kind", "porcelain_bonded"); await expect(page.getByTestId("tooth-crown-UR6")).toHaveAttribute("fill", crownFill!);
  for (const surface of ["M", "O", "D"]) await expect(page.getByTestId(`clinical-surface-fill-LR6-${surface}`)).toHaveAttribute("fill", surfaceFill!);
  for (const theme of ["light", "dark"]) {
    await page.evaluate((value) => document.documentElement.dataset.theme = value, theme); await page.evaluate(() => scrollTo(0, 0));
    await page.getByTestId("clinical-chart").screenshot({ path: path.join(previews, `${theme}-current-completed-materials.png`) });
  }
  await view(page, "planned");
  for (const theme of ["light", "dark"]) {
    await page.evaluate((value) => document.documentElement.dataset.theme = value, theme); await page.evaluate(() => scrollTo(0, 0));
    await page.getByTestId("treatment-planning-chart").screenshot({ path: path.join(previews, `${theme}-completed-materials.png`) });
  }
  await reload(page); await expect(page.getByTestId("clinical-crown-UR6")).toHaveAttribute("data-crown-kind", "porcelain_bonded");
  await undo(page, value, completedFilling); await expect(page.getByTestId("clinical-surface-LR6-M")).toHaveAttribute("data-surface-kind", "carious");
  for (const surface of ["O", "D"]) await expect(page.getByTestId(`clinical-surface-LR6-${surface}`)).toHaveAttribute("data-surface-kind", "untouched");
  await undo(page, value, completedCrown); await expect(page.getByTestId("clinical-crown-UR6")).toHaveAttribute("data-crown-kind", "untouched");
  await expect(page.getByTestId("planning-action-material")).toBeEnabled(); await unchanged(request, value, original, captured);
  await view(page, "current"); await expect(page.getByTestId("clinical-crown-UR6")).toHaveAttribute("data-crown-kind", "untouched");
  await expect(page.getByTestId("clinical-surface-LR6-M")).toHaveAttribute("data-surface-kind", "carious");
  for (const surface of ["O", "D"]) await expect(page.getByTestId(`clinical-surface-LR6-${surface}`)).toHaveAttribute("data-surface-kind", "untouched");
});

test("undo reprojects remaining completions in active procedure order instead of erasing an earlier completed crown", async ({ page, request }) => {
  const value = await fixture(page, request), crownTreatment = await catalogue(request, value, "crown", "ordered-crown"), extractionTreatment = await catalogue(request, value, "tooth", "ordered-extraction");
  const original = await native(request, value), captured = await start(page, request, value);
  const crownItem = await add(page, value, crownTreatment, { level: "crown", tooth: "UR6", surfaces: [] }, "crown", "gold");
  const completedCrown = await complete(page, value, crownItem); await expect(page.getByTestId("clinical-crown-UR6")).toHaveAttribute("data-crown-kind", "gold");
  const extractionItem = await add(page, value, extractionTreatment, { level: "tooth", tooth: "UR6", surfaces: [] }, "extraction");
  const completedExtraction = await complete(page, value, extractionItem); expect(completedExtraction.completed_procedure_id!).toBeGreaterThan(completedCrown.completed_procedure_id!);
  await expect(page.getByTestId("planning-tooth-UR6")).toHaveAttribute("data-projected-completion-ids", `${completedCrown.completed_procedure_id},${completedExtraction.completed_procedure_id}`);
  await expect(page.getByTestId("tooth-svg-UR6")).toHaveAttribute("data-baseline-status", "missing");
  await view(page, "current"); await expect(page.getByTestId("tooth-svg-UR6")).toHaveAttribute("data-baseline-status", "missing"); await view(page, "planned");
  await undo(page, value, completedExtraction); await expect(page.getByTestId("clinical-crown-UR6")).toHaveAttribute("data-crown-kind", "gold");
  await expect(page.getByTestId("planning-tooth-UR6")).toHaveAttribute("data-projected-completion-ids", String(completedCrown.completed_procedure_id));
  await reload(page); await expect(page.getByTestId("clinical-crown-UR6")).toHaveAttribute("data-crown-kind", "gold");
  await view(page, "current"); await expect(page.getByTestId("clinical-crown-UR6")).toHaveAttribute("data-crown-kind", "gold"); await view(page, "planned");
  await undo(page, value, completedCrown); await expect(page.getByTestId("clinical-crown-UR6")).toHaveAttribute("data-crown-kind", "untouched");
  await expect(page.getByTestId("planning-tooth-UR6")).toHaveAttribute("data-projected-completion-ids", ""); await unchanged(request, value, original, captured);
  await view(page, "current"); await expect(page.getByTestId("clinical-crown-UR6")).toHaveAttribute("data-crown-kind", "untouched");
});

test("later Current surface findings survive undo while movement alone cannot resurrect a completed extraction", async ({ page, request }) => {
  const value = await fixture(page, request);
  await record(request, value, "surface-conditions", { targets: [{ tooth: "LR6", surfaces: ["M"] }], observation: { kind: "carious", material: null, condition: "carious_established", defects: [] }, expected_revisions: { LR6: 0 } });
  const fillingTreatment = await catalogue(request, value, "surface", "later-filling"), extractionTreatment = await catalogue(request, value, "tooth", "later-extraction");
  const captured = await start(page, request, value);
  const filling = await add(page, value, fillingTreatment, { level: "surface", tooth: "LR6", surfaces: ["M"] }, "filling", "gold");
  const completedFilling = await complete(page, value, filling);
  await view(page, "current"); await expect(page.getByTestId("clinical-surface-LR6-M")).toHaveAttribute("data-surface-material", "gold");
  await page.getByTestId("clinical-surface-LR6-M").click({ button: "right" });
  const menu = page.getByTestId("clinical-surface-action-menu"); await expect(menu).toBeVisible();
  await expect(menu.getByTestId("clinical-surface-material")).toHaveValue("gold"); await menu.getByTestId("clinical-surface-material").selectOption("amalgam");
  const surfaceSaved = page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === `/api/patients/${value.id}/clinical/surface-conditions`);
  await menu.getByTestId("clinical-surface-apply").click(); const surfaceResponse = await surfaceSaved; expect(surfaceResponse.ok()).toBeTruthy();
  expect(surfaceResponse.request().postDataJSON()).toMatchObject({ expected_projection_revision: expect.any(Number), observation: { kind: "restored", material: "amalgam", condition: "sound", defects: [] } });
  await expect(page.getByTestId("clinical-surface-LR6-M")).toHaveAttribute("data-surface-material", "amalgam");
  const afterSurfaceEdit = await native(request, value); expect(afterSurfaceEdit.teeth.LR6.surface_observations?.M?.material).toBe("amalgam");
  await view(page, "planned"); await undo(page, value, completedFilling);
  await view(page, "current"); await expect(page.getByTestId("clinical-surface-LR6-M")).toHaveAttribute("data-surface-material", "amalgam");
  expect((await native(request, value)).teeth).toEqual(afterSurfaceEdit.teeth);
  await view(page, "planned");
  const extraction = await add(page, value, extractionTreatment, { level: "tooth", tooth: "UR6", surfaces: [] }, "extraction");
  const completedExtraction = await complete(page, value, extraction);
  await view(page, "current"); await expect(page.getByTestId("tooth-svg-UR6")).toHaveAttribute("data-baseline-status", "missing");
  await page.getByTestId("diagnosis-level-tooth").click(); await page.getByTestId("diagnosis-palette-movement_forward").click(); await page.getByTestId("tooth-label-UR6").click();
  const movementSaved = page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === `/api/patients/${value.id}/clinical/tooth-conditions`);
  await page.getByTestId("diagnosis-apply").click(); const movementResponse = await movementSaved; expect(movementResponse.ok()).toBeTruthy();
  expect(movementResponse.request().postDataJSON()).toMatchObject({ expected_projection_revision: expect.any(Number), teeth: ["UR6"], movement: "forward" });
  await expect(page.getByTestId("tooth-svg-UR6")).toHaveAttribute("data-baseline-status", "missing"); await expect(page.getByTestId("tooth-crown-UR6")).toHaveCount(0);
  await expect(page.getByTestId("tooth-movement-UR6")).toBeAttached();
  await page.reload({ waitUntil: "domcontentloaded" }); await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("tooth-svg-UR6")).toHaveAttribute("data-baseline-status", "missing");
  const afterMovementEdit = await native(request, value);
  await view(page, "planned"); await undo(page, value, completedExtraction);
  await view(page, "current"); await expect(page.getByTestId("tooth-crown-UR6")).toBeAttached(); await expect(page.getByTestId("tooth-movement-UR6")).toBeAttached();
  await expect(page.getByTestId("clinical-surface-LR6-M")).toHaveAttribute("data-surface-material", "amalgam");
  await unchanged(request, value, afterMovementEdit, captured);
});

test("refreshing a changed completion projection clears stale Current surface drafts before a new edit", async ({ page, request }) => {
  const value = await fixture(page, request), writes: string[] = [];
  let projectionRevision = 20;
  let material = "gold";
  await page.route(`**/api/patients/${value.id}/clinical/tooth-conditions`, async (route) => {
    if (route.request().method() !== "GET") { writes.push(route.request().method()); await route.fulfill({ status: 500, json: { detail: "This inspection must not write" } }); return; }
    await route.fulfill({ json: { patient_id: Number(value.id), teeth: {}, note_teeth: [], bridges: [],
      completed_effects: [{ item_id: 900, procedure_id: projectionRevision * 40, completed_at: "2030-01-07T09:00:00Z", event_id: projectionRevision, target: { level: "surface", tooth: "LR6", surfaces: ["M"] }, drawing_kind: "filling", material }],
      observation_events: {}, projection_revision: projectionRevision, projection_coverage: { status: "available", reason: null } } });
  });
  await page.goto(`${getBaseUrl()}/patients/${value.id}/clinical?clinicalView=current`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("clinical-surface-LR6-M")).toHaveAttribute("data-surface-material", "gold");
  await page.getByTestId("clinical-surface-LR6-M").click({ button: "right" });
  await expect(page.getByTestId("clinical-surface-action-menu").getByTestId("clinical-surface-material")).toHaveValue("gold");
  await expect(page.getByTestId("clinical-surface-LR6-M")).toHaveAttribute("aria-pressed", "true");
  projectionRevision = 21; material = "amalgam";
  await page.getByTestId("clinical-data-refresh").click();
  await expect(page.getByTestId("clinical-surface-action-menu")).toHaveCount(0);
  await expect(page.getByTestId("clinical-surface-LR6-M")).toHaveAttribute("data-surface-material", "amalgam");
  await expect(page.getByTestId("clinical-surface-LR6-M")).toHaveAttribute("aria-pressed", "false");
  await page.getByTestId("clinical-surface-LR6-M").click({ button: "right" });
  await expect(page.getByTestId("clinical-surface-action-menu").getByTestId("clinical-surface-material")).toHaveValue("amalgam");
  await page.getByTestId("clinical-surface-action-menu").getByRole("button", { name: "Cancel", exact: true }).click();
  expect(writes).toEqual([]);
});
