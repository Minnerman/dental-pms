import { expect, test, type APIRequestContext, type Page, type Route } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";
import type { PlanningCatalogue, PlanningCatalogueItem, PlanningFee, PlanningItem, PlanningResponse, PlanningSnapshot } from "../components/clinical/treatmentPlanning";

const fixed: PlanningFee = { type: "FIXED", amount_pence: 12500, min_amount_pence: null, max_amount_pence: null, notes: "Synthetic category fee" };
function entry(id: number, name: string, fee = fixed): PlanningCatalogueItem { return { id, name, code: `SYN${id}`, description: "Synthetic treatment for isolated testing", default_duration_minutes: 30, patient_category: "CLINIC_PRIVATE", fee: { ...fee }, quote_token: String(id).repeat(64).slice(0, 64) }; }
function captured(id: string): PlanningSnapshot { return { version: 1, captured_at: "2026-09-01T09:30:00Z", native: { patient_id: Number(id), teeth: { UR4: { revision: 1, condition: "missing" }, LL5: { revision: 1, condition: "unerupted", dentition: "deciduous" } }, note_teeth: [], bridges: [] }, legacy: null, coverage: { native: "captured", legacy: "unavailable", legacy_reason: "No imported chart is attached to this synthetic patient." } }; }
type Write = { method: string; path: string; body: Record<string, unknown>; requestId: string | undefined };
type Mock = { id: string; headers: Record<string, string>; state: PlanningResponse; catalogue: PlanningCatalogue; writes: Write[]; intercept: ((route: Route, write: Write) => Promise<boolean>) | null };

async function setup(page: Page, request: APIRequestContext) {
  const token = await primePageAuth(page, request);
  const id = await createPatient(request, { first_name: "Synthetic", last_name: `Planning ${Date.now()}` });
  await page.setViewportSize({ width: 1600, height: 1100 });
  return { id, headers: { Authorization: `Bearer ${token}` } };
}
async function mock(page: Page, request: APIRequestContext, started = true): Promise<Mock> {
  const { id, headers } = await setup(page, request);
  const state: PlanningResponse = { patient_id: Number(id), plan: started ? { id: 10, created_at: "2026-09-01T09:30:00Z", created_by: null, snapshot: captured(id), items: [] } : null, earlier_items: [], earlier_items_total: 0 };
  const catalogue: PlanningCatalogue = { patient_id: Number(id), patient_category: "CLINIC_PRIVATE", currency: "GBP", total: 4, items: [entry(1, "Sample restoration"), entry(2, "Sample range", { ...fixed, type: "RANGE", amount_pence: null, min_amount_pence: 10000, max_amount_pence: 20000 }), entry(3, "Sample unpriced", { ...fixed, type: "UNAVAILABLE", amount_pence: null }), entry(4, "Sample zero", { ...fixed, amount_pence: 0 })] };
  const result: Mock = { id, headers, state, catalogue, writes: [], intercept: null };
  await page.route(`**/api/patients/${id}/planning**`, async (route) => {
    const req = route.request(), url = new URL(req.url()), endpoint = `/api/patients/${id}/planning`;
    if (req.method() === "GET") {
      if (url.pathname.endsWith("/catalogue")) { const q = url.searchParams.get("q")?.toLowerCase() ?? ""; const items = catalogue.items.filter((item) => `${item.name} ${item.code}`.toLowerCase().includes(q)); await route.fulfill({ json: { ...catalogue, items, total: items.length } }); }
      else await route.fulfill({ json: state });
      return;
    }
    const write: Write = { method: req.method(), path: url.pathname, body: req.postDataJSON(), requestId: req.headers()["request-id"] }; result.writes.push(write);
    if (result.intercept && await result.intercept(route, write)) return;
    if (url.pathname === `${endpoint}/start`) { state.plan = state.plan ?? { id: 10, created_at: "2026-09-01T09:30:00Z", created_by: null, snapshot: captured(id), items: [] }; await route.fulfill({ status: 201, json: state }); return; }
    if (req.method() === "POST") {
      const treatment = catalogue.items.find((item) => item.id === write.body.treatment_id)!;
      const target = write.body.target as PlanningItem["target"];
      const item: PlanningItem = { id: 100 + state.plan!.items.length, patient_id: Number(id), plan_id: 10, treatment_id: treatment.id, revision: 1, target, tooth: target.tooth, surface: target.surfaces.join("") || null, drawing_kind: write.body.drawing_kind as PlanningItem["drawing_kind"], procedure_code: treatment.code!, description: treatment.name, status: "proposed", fee_pence: write.body.fee_mode === "catalogue" ? treatment.fee.amount_pence : Number(write.body.fee_pence), fee_mode: write.body.fee_mode as PlanningItem["fee_mode"], fee_reason: write.body.fee_reason as string | null, catalogue_snapshot: treatment, completed_procedure_id: null, created_at: "2026-09-01T10:00:00Z", updated_at: "2026-09-01T10:00:00Z" };
      state.plan!.items.push(item); await route.fulfill({ status: 201, json: item }); return;
    }
    const item = state.plan!.items.find((value) => value.id === Number(url.pathname.split("/").pop()))!;
    if (write.body.expected_revision !== item.revision) { await route.fulfill({ status: 409, json: { detail: "Synthetic revision conflict" } }); return; }
    if (write.body.status) item.status = write.body.status as PlanningItem["status"];
    if (write.body.fee_mode) { item.fee_mode = write.body.fee_mode as PlanningItem["fee_mode"]; item.fee_pence = item.fee_mode === "catalogue" ? item.catalogue_snapshot.fee.amount_pence : Number(write.body.fee_pence); item.fee_reason = write.body.fee_reason as string | null; }
    item.revision += 1; await route.fulfill({ json: item });
  });
  return result;
}
async function open(page: Page, id: string) {
  await page.goto(`${getBaseUrl()}/patients/${id}/clinical?clinicalView=planned`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("treatment-planning-panel")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("planning-loading")).toHaveCount(0, { timeout: 30_000 });
}
async function choose(page: Page, treatment = 1) {
  await page.getByTestId("planning-add-treatment").click();
  await expect(page.getByTestId("planning-treatment-dialog")).toBeVisible();
  await page.getByTestId(`planning-catalogue-item-${treatment}`).click();
}
async function save(page: Page, id: number) { await page.getByTestId("planning-save").click(); await expect(page.getByTestId("planning-treatment-dialog")).toBeHidden(); await expect(page.getByTestId(`planning-item-${id}`)).toBeVisible(); }
async function noPageOverflow(page: Page) { await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1); }

test("planning starts once with a frozen baseline and four independently selectable levels", async ({ page, request }) => {
  const harness = await mock(page, request, false); await open(page, harness.id);
  await expect(page.getByTestId("planning-not-started")).toBeVisible(); expect(harness.writes).toHaveLength(0);
  await page.getByTestId("planning-start").click(); await expect(page.getByTestId("treatment-planning-chart")).toBeVisible();
  expect(harness.writes).toHaveLength(1); expect(harness.writes[0].path).toMatch(/\/start$/);
  const chart = page.getByTestId("treatment-planning-chart");
  await expect(chart).toHaveAttribute("data-snapshot-captured-at", "2026-09-01T09:30:00Z");
  await expect(chart.getByTestId("tooth-svg-UR4")).toHaveAttribute("data-baseline-status", "missing");
  for (const level of ["tooth", "root", "crown", "surface"]) { await page.getByTestId(`planning-level-${level}`).click(); await expect(page.getByTestId(`planning-level-${level}`)).toHaveAttribute("aria-selected", "true"); }
  await page.getByTestId("planning-level-surface").focus(); await page.keyboard.press("Home"); await expect(page.getByTestId("planning-level-tooth")).toBeFocused();
  await page.reload({ waitUntil: "domcontentloaded" }); await expect(chart).toBeVisible({ timeout: 30_000 }); expect(harness.writes).toHaveLength(1);
  await expect(page.getByTestId("clinical-diagnosis-palette")).toHaveCount(0);
  await expect(page.getByTestId("planning-start")).toHaveCount(0);
  await page.getByTestId("planning-add-treatment").click(); await page.getByTestId("planning-target-level").selectOption("tooth");
  await expect(page.getByTestId("planning-target-tooth").locator('option[value="LL5"]')).toHaveText("LLE (chart position LL5)");
  await page.getByTestId("planning-target-tooth").selectOption("LL5"); await expect(page.getByTestId("planning-target-tooth")).toHaveValue("LL5");
  await page.getByTestId("planning-cancel").click(); expect(harness.writes).toHaveLength(1);
});

test("catalogue treatment and explicit multi-surface drawing save one plan item without diagnosis or finance writes", async ({ page, request }) => {
  const harness = await mock(page, request); await open(page, harness.id);
  const mutations: string[] = []; page.on("request", (req) => { if (["POST", "PATCH", "PUT", "DELETE"].includes(req.method())) mutations.push(new URL(req.url()).pathname); });
  await page.getByTestId("clinical-surface-UR6-M").click({ button: "right" });
  await expect(page.getByTestId("planning-target-level")).toHaveValue("surface");
  await expect(page.getByTestId("planning-target-tooth")).toHaveValue("UR6");
  await page.getByTestId("planning-catalogue-search").fill("Sample restoration");
  await page.getByTestId("planning-catalogue-item-1").click();
  await expect(page.getByTestId("planning-drawing-kind")).toHaveValue(""); await expect(page.getByTestId("planning-save")).toBeDisabled();
  await page.getByTestId("planning-drawing-kind").selectOption("filling");
  await page.getByTestId("planning-target-surface-O").check(); await page.getByTestId("planning-target-surface-D").check();
  expect(harness.writes).toHaveLength(0); await save(page, 100);
  expect(harness.writes[0].body).toEqual({ treatment_id: 1, quote_token: "1".repeat(64), target: { level: "surface", tooth: "UR6", surfaces: ["M", "O", "D"] }, drawing_kind: "filling", fee_mode: "catalogue", fee_reason: null });
  expect(mutations).toEqual([`/api/patients/${harness.id}/planning/items`]);
  await expect(page.getByTestId("tooth-planning-overlay-UR6-100")).toHaveAttribute("data-plan-status", "planned");
  await expect(page.getByTestId("planning-total-outstanding")).toHaveText("£125.00"); await expect(page.getByTestId("planning-total-completed")).toHaveText("£0.00");
  await expect(page.getByTestId("clinical-surface-UR6-M")).toHaveAttribute("data-surface-recorded", "false");
});

test("range agreed fee override waiver and genuine catalogue zero remain explicit and preserve saved quotes", async ({ page, request }) => {
  const harness = await mock(page, request); await open(page, harness.id);
  await choose(page, 2); await expect(page.getByTestId("planning-fee-mode")).toHaveValue("agreed"); await expect(page.getByTestId("planning-save")).toBeDisabled();
  await page.getByTestId("planning-fee-amount").fill("220"); await expect(page.getByTestId("planning-validation")).toContainText("outside the quoted range");
  await page.getByTestId("planning-fee-amount").fill("150"); await save(page, 100);
  await page.getByTestId("planning-edit-fee-100").click(); await page.getByTestId("planning-fee-mode").selectOption("override"); await page.getByTestId("planning-fee-amount").fill("220");
  await expect(page.getByTestId("planning-save")).toBeDisabled(); await page.getByTestId("planning-fee-reason").fill("Synthetic additional complexity agreed"); await save(page, 100);
  expect(harness.state.plan!.items[0].catalogue_snapshot.fee).toEqual(harness.catalogue.items[1].fee); expect(harness.state.plan!.items[0].fee_pence).toBe(22000);
  await page.getByTestId("planning-edit-fee-100").click(); await page.getByTestId("planning-fee-mode").selectOption("waived"); await page.getByTestId("planning-fee-reason").fill(""); await expect(page.getByTestId("planning-save")).toBeDisabled();
  await page.getByTestId("planning-fee-reason").fill("Synthetic waiver authorised"); await save(page, 100); await expect(page.getByTestId("planning-item-100")).toContainText("Waived fee");
  await choose(page, 3); await page.getByTestId("planning-fee-amount").fill("10"); await expect(page.getByTestId("planning-save")).toBeDisabled(); await page.getByTestId("planning-fee-reason").fill("Synthetic agreed fee with no price list entry"); await save(page, 101);
  await choose(page, 4); await expect(page.getByTestId("planning-fee-mode")).toHaveValue("catalogue"); await save(page, 102);
  expect(harness.state.plan!.items[2].fee_pence).toBe(0); expect(harness.state.plan!.items[2].fee_mode).toBe("catalogue");
  await choose(page, 1); await save(page, 103); await page.getByTestId("planning-edit-fee-103").click();
  await page.getByTestId("planning-fee-mode").selectOption("override"); await page.getByTestId("planning-fee-amount").fill("80"); await page.getByTestId("planning-fee-reason").fill("Synthetic temporary override"); await save(page, 103);
  await page.getByTestId("planning-edit-fee-103").click(); await page.getByTestId("planning-fee-mode").selectOption("catalogue"); await expect(page.getByTestId("planning-fee-reason")).toHaveCount(0); await save(page, 103);
  expect(harness.writes.at(-1)!.body).toEqual({ expected_revision: 2, fee_mode: "catalogue", fee_reason: null });
  expect(harness.state.plan!.items[3]).toMatchObject({ fee_mode: "catalogue", fee_pence: 12500, fee_reason: null });
  await page.reload({ waitUntil: "domcontentloaded" }); await expect(page.getByTestId("planning-item-100")).toContainText("Synthetic waiver authorised", { timeout: 30_000 });
});

test("planning rejects stale revisions and retries an uncertain unchanged save with the same request identity", async ({ page, request }) => {
  const harness = await mock(page, request); await open(page, harness.id); await choose(page); await save(page, 100);
  harness.intercept = async (route, write) => { if (write.method === "PATCH") { await route.fulfill({ status: 409, json: { detail: "Synthetic changed revision" } }); return true; } return false; };
  await page.getByTestId("planning-edit-fee-100").click(); await page.getByTestId("planning-fee-mode").selectOption("override"); await page.getByTestId("planning-fee-amount").fill("80"); await page.getByTestId("planning-fee-reason").fill("Synthetic revised quote");
  await page.getByTestId("planning-save").click(); await expect(page.getByTestId("planning-error")).toContainText("changed"); expect(harness.state.plan!.items[0].fee_pence).toBe(12500); await page.getByTestId("planning-cancel").click();
  let failures = 0; harness.intercept = async (route, write) => { if (write.method === "POST" && failures++ === 0) { await route.fulfill({ status: 503, json: { detail: "Synthetic uncertain response" } }); return true; } return false; };
  await choose(page); await page.getByTestId("planning-save").click(); await expect(page.getByTestId("planning-error")).toContainText("could not be confirmed"); await expect(page.getByTestId("planning-target-level")).toBeDisabled();
  await page.getByTestId("planning-save").click(); await expect(page.getByTestId("planning-treatment-dialog")).toBeHidden();
  const writes = harness.writes.filter((write) => write.method === "POST").slice(-2); expect(writes[0].requestId).toBeTruthy(); expect(writes[0].requestId).toBe(writes[1].requestId); expect(writes[0].body).toEqual(writes[1].body); expect(harness.state.plan!.items).toHaveLength(2);
});

test("pending plan saves lock fields Escape tabs and duplicate submission until the response completes", async ({ page, request }) => {
  const harness = await mock(page, request); await open(page, harness.id); await choose(page);
  let release!: () => void; const gate = new Promise<void>((resolve) => { release = resolve; });
  harness.intercept = async (_route, write) => { if (write.method === "POST") await gate; return false; };
  try {
    await page.getByTestId("planning-save").click(); await expect(page.getByTestId("planning-save")).toBeDisabled(); await expect(page.getByTestId("planning-cancel")).toBeDisabled(); await expect(page.getByTestId("planning-target-level")).toBeDisabled();
    await page.keyboard.press("Control+1"); await page.keyboard.press("Meta+1");
    await expect(page.getByTestId("treatment-planning-panel")).toBeVisible(); await expect(page.getByTestId("planning-treatment-dialog")).toBeVisible();
    await page.keyboard.press("Escape"); await page.keyboard.press("Enter"); await page.keyboard.press("Tab");
    await expect(page.getByTestId("planning-treatment-dialog")).toBeVisible(); await expect(page.getByTestId("planning-treatment-dialog")).toBeFocused(); await expect(page.getByTestId("planning-level-root")).toBeDisabled(); expect(harness.writes).toHaveLength(1);
  } finally { release(); }
  await expect(page.getByTestId("planning-treatment-dialog")).toBeHidden(); await expect(page.getByTestId("planning-item-100")).toBeVisible();
});

test("read-only earlier items and failed catalogue loads never become an empty successful plan", async ({ page, request }) => {
  const harness = await mock(page, request);
  harness.state.earlier_items = [{ id: 90, patient_id: Number(harness.id), tooth: "LL6", surface: null, procedure_code: "SYN-OLD", description: "Synthetic earlier proposal", fee_pence: null, status: "proposed", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" }]; harness.state.earlier_items_total = 1;
  await page.route("**/api/me/capabilities", (route) => route.fulfill({ json: ["patients.view", "clinical.view", "notes.view"] }));
  await open(page, harness.id); await expect(page.getByTestId("planning-read-only")).toBeVisible(); await expect(page.getByTestId("planning-add-treatment")).toBeDisabled();
  await page.getByTestId("planning-earlier-items").locator("summary").click(); await expect(page.getByTestId("planning-earlier-items")).toContainText("Not priced"); await expect(page.getByTestId("tooth-planning-overlay-LL6-90")).toHaveCount(0); expect(harness.writes).toHaveLength(0);
  await page.unroute("**/api/me/capabilities"); await page.reload({ waitUntil: "domcontentloaded" }); await expect(page.getByTestId("planning-add-treatment")).toBeEnabled({ timeout: 30_000 });
  await page.route(`**/api/patients/${harness.id}/planning/catalogue?**`, (route) => route.fulfill({ status: 503, json: { detail: "Synthetic unavailable catalogue" } }));
  await page.getByTestId("planning-add-treatment").click(); await expect(page.getByTestId("planning-treatment-dialog").getByRole("alert")).toContainText("catalogue could not be loaded"); await expect(page.getByTestId("planning-save")).toBeDisabled(); expect(harness.writes).toHaveLength(0);
});

test("real synthetic plan snapshots diagnosis and completes one saved fee into procedure and finance exactly once", async ({ page, request }) => {
  const { id, headers } = await setup(page, request), base = getBaseUrl(), endpoint = `${base}/api/patients/${id}`;
  const recorded = await request.post(`${endpoint}/clinical/tooth-conditions`, { headers, data: { teeth: ["UR4"], condition: "missing", expected_revisions: { UR4: 0 } } }); expect(recorded.ok()).toBeTruthy();
  const treatment = await request.post(`${base}/api/treatments`, { headers, data: { name: `Synthetic plan catalogue ${id}`, code: `SYN-${id}`, is_active: true } }); expect(treatment.ok()).toBeTruthy(); const treatmentId = (await treatment.json()).id;
  const fees = await request.put(`${base}/api/treatments/${treatmentId}/fees`, { headers, data: [{ patient_category: "CLINIC_PRIVATE", fee_type: "FIXED", amount_pence: 8700 }] }); expect(fees.ok()).toBeTruthy();
  await open(page, id); await page.getByTestId("planning-start").click(); await expect(page.getByTestId("treatment-planning-chart")).toBeVisible();
  const changed = await request.post(`${endpoint}/clinical/tooth-conditions`, { headers, data: { teeth: ["UR4"], condition: "unrecorded", expected_revisions: { UR4: 1 } } }); expect(changed.ok()).toBeTruthy();
  await page.getByTestId("planning-refresh").click(); await expect(page.getByTestId("treatment-planning-chart").getByTestId("tooth-svg-UR4")).toHaveAttribute("data-baseline-status", "missing");
  await page.getByTestId("planning-tooth-number-UR4").click(); await page.getByTestId("planning-catalogue-search").fill(`Synthetic plan catalogue ${id}`); await page.getByTestId(`planning-catalogue-item-${treatmentId}`).click(); await page.getByTestId("planning-drawing-kind").selectOption("implant");
  await page.getByTestId("planning-save").click(); await expect(page.getByTestId("planning-treatment-dialog")).toBeHidden();
  const workspace = await request.get(`${endpoint}/planning`, { headers }); expect(workspace.ok()).toBeTruthy(); const item = (await workspace.json()).plan.items[0] as PlanningItem;
  await page.getByTestId(`planning-edit-fee-${item.id}`).click(); await page.getByTestId("planning-fee-mode").selectOption("override"); await page.getByTestId("planning-fee-amount").fill("82"); await page.getByTestId("planning-fee-reason").fill("Synthetic patient-specific agreed adjustment"); await save(page, item.id);
  await page.getByTestId(`planning-edit-fee-${item.id}`).click(); await page.getByTestId("planning-fee-mode").selectOption("catalogue"); await expect(page.getByTestId("planning-fee-reason")).toHaveCount(0); await save(page, item.id);
  await expect(page.getByTestId(`planning-item-${item.id}`)).toContainText("£87.00");
  await page.getByTestId(`planning-edit-fee-${item.id}`).click(); await page.getByTestId("planning-fee-mode").selectOption("override"); await page.getByTestId("planning-fee-amount").fill("82"); await page.getByTestId("planning-fee-reason").fill("Synthetic patient-specific agreed adjustment"); await save(page, item.id);
  const before = await request.get(`${endpoint}/ledger`, { headers }); expect((await before.json()).filter((row: { reference: string }) => row.reference === `TREATMENT-PLAN:${item.id}`)).toHaveLength(0);
  let confirmation = ""; page.once("dialog", async (value) => { confirmation = value.message(); await value.accept(); }); await page.getByTestId(`planning-complete-${item.id}`).click();
  await expect(page.getByTestId(`planning-item-${item.id}`)).toHaveAttribute("data-status", "completed"); expect(confirmation).toContain("£82.00"); await expect(page.getByTestId(`tooth-planning-overlay-UR4-${item.id}`)).toHaveAttribute("data-plan-status", "completed");
  await page.getByTestId("planning-refresh").click();
  const [ledger, clinical, conditions, unchangedFees] = await Promise.all([request.get(`${endpoint}/ledger`, { headers }), request.get(`${endpoint}/clinical/summary?limit=200`, { headers }), request.get(`${endpoint}/clinical/tooth-conditions`, { headers }), request.get(`${base}/api/treatments/${treatmentId}/fees`, { headers })]);
  const charges = (await ledger.json()).filter((row: { reference: string }) => row.reference === `TREATMENT-PLAN:${item.id}`); expect(charges).toHaveLength(1); expect(charges[0].amount_pence).toBe(8200);
  expect((await clinical.json()).recent_procedures.filter((row: { procedure_code: string }) => row.procedure_code === `SYN-${id}`)).toHaveLength(1); expect((await conditions.json()).teeth.UR4.condition).toBe("unrecorded"); expect((await unchangedFees.json())[0].amount_pence).toBe(8700);
  const historyResponse = await request.get(`${endpoint}/planning/items/${item.id}/history`, { headers }); expect(historyResponse.ok()).toBeTruthy();
  const versions = (await historyResponse.json()).items as { revision: number; snapshot: PlanningItem }[];
  expect(versions.find((version) => version.revision === 2)?.snapshot).toMatchObject({ fee_mode: "override", fee_pence: 8200, fee_reason: "Synthetic patient-specific agreed adjustment" });
  expect(versions.find((version) => version.revision === 3)?.snapshot).toMatchObject({ fee_mode: "catalogue", fee_pence: 8700, fee_reason: null });
});

test("planning chart catalogue and fee editor fit light dark and narrow screens with the notes sidebar retained", async ({ page, request }) => {
  const harness = await mock(page, request); await open(page, harness.id);
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.getByTestId("planning-add-treatment").click(); await expect(page.getByTestId("planning-treatment-dialog")).toBeVisible(); await page.getByTestId("planning-cancel").click(); await noPageOverflow(page);
  await page.setViewportSize({ width: 1600, height: 1100 });
  await page.getByTestId("planning-tooth-number-UR6").click(); await page.getByTestId("planning-catalogue-item-1").click(); await page.getByTestId("planning-drawing-kind").selectOption("implant"); await save(page, 100);
  await page.getByTestId("clinical-root-LR6").click(); await page.getByTestId("planning-catalogue-item-1").click(); await page.getByTestId("planning-drawing-kind").selectOption("root_canal"); await save(page, 101);
  const previews = path.join(process.cwd(), ".run", "planning-previews"); await mkdir(previews, { recursive: true });
  await page.getByTestId("clinical-notes-body").fill("Synthetic draft retained beside planned treatment.");
  await page.getByTestId("clinical-chart-view-current").click(); await expect(page.getByTestId("clinical-diagnosis-levels")).toBeVisible();
  await expect(page.getByTestId("clinical-notes-body")).toHaveValue("Synthetic draft retained beside planned treatment.");
  await page.getByTestId("clinical-chart-view-planned").click(); await expect(page.getByTestId("treatment-planning-chart")).toBeVisible();
  await expect(page.getByTestId("clinical-notes-body")).toHaveValue("Synthetic draft retained beside planned treatment.");
  for (const theme of ["light", "dark"]) { await page.evaluate((value) => document.documentElement.dataset.theme = value, theme); await page.evaluate(() => scrollTo(0, 0)); await page.screenshot({ path: path.join(previews, `planning-${theme}-wide.png`), fullPage: true }); await noPageOverflow(page); }
  await page.getByTestId("planning-add-treatment").click(); await page.getByTestId("planning-catalogue-item-2").click(); await page.screenshot({ path: path.join(previews, "planning-catalogue-dark.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 }); await page.getByTestId("planning-cancel").scrollIntoViewIfNeeded(); const cancel = (await page.getByTestId("planning-cancel").boundingBox())!; expect(cancel.x).toBeGreaterThanOrEqual(0); expect(cancel.x + cancel.width).toBeLessThanOrEqual(390); await noPageOverflow(page);
  await page.screenshot({ path: path.join(previews, "planning-editor-mobile.png"), fullPage: true }); await page.getByTestId("planning-cancel").click();
  await expect(page.getByTestId("clinical-notes-body")).toHaveValue("Synthetic draft retained beside planned treatment."); await noPageOverflow(page);
});
