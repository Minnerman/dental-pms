import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";
import type { PlanningCatalogueItem, PlanningItem, PlanningResponse } from "../components/clinical/treatmentPlanning";

async function fixture(page: Page, request: APIRequestContext) {
  const token = await primePageAuth(page, request);
  const id = await createPatient(request, { first_name: "Synthetic", last_name: `Anatomical Other ${Date.now()}` });
  await page.setViewportSize({ width: 1600, height: 1100 });
  return { id, headers: { Authorization: `Bearer ${token}` } };
}
async function open(page: Page, id: string) {
  await page.goto(`${getBaseUrl()}/patients/${id}/clinical?clinicalView=planned`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("treatment-planning-panel")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("planning-loading")).toHaveCount(0, { timeout: 30_000 });
}

test("real Other treatment keeps the selected tooth root crown or surface and never changes diagnosis or charges on proposal", async ({ page, request }) => {
  const { id, headers } = await fixture(page, request), endpoint = `${getBaseUrl()}/api/patients/${id}`;
  const before = await request.get(`${endpoint}/clinical/tooth-conditions`, { headers }); expect(before.ok()).toBeTruthy(); const baseline = await before.json();
  await open(page, id); await page.getByTestId("planning-start").click(); await expect(page.getByTestId("treatment-planning-chart")).toBeVisible();
  const targets = [
    { level: "tooth", testid: "planning-tooth-number-UR6", surfaces: [] },
    { level: "root", testid: "clinical-root-UR6", surfaces: [] },
    { level: "crown", testid: "clinical-crown-UR6", surfaces: [] },
    { level: "surface", testid: "clinical-surface-UR6-M", surfaces: ["M"] },
  ];
  for (const target of targets) {
    await page.getByTestId(`planning-level-${target.level}`).click(); await page.getByTestId(target.testid).click({ button: "right" });
    await expect(page.getByTestId("planning-treatment-dialog")).toBeVisible(); await expect(page.getByTestId("planning-target-level")).toHaveValue(target.level); await expect(page.getByTestId("planning-target-tooth")).toHaveValue("UR6");
    await page.getByTestId("planning-other-treatment").click(); await expect(page.getByTestId("planning-other-description")).toBeVisible(); await expect(page.getByTestId("planning-save")).toBeDisabled();
    const description = `Synthetic ${target.level} custom treatment ${id}`;
    await page.getByTestId("planning-other-description").fill(description); await page.getByTestId("planning-fee-amount").fill("21.25");
    const responsePromise = page.waitForResponse((response) => response.request().method() === "POST" && response.url().endsWith(`/api/patients/${id}/planning/custom-items`));
    await page.getByTestId("planning-save").click(); const response = await responsePromise; expect(response.ok()).toBeTruthy();
    const payload = response.request().postDataJSON(); expect(payload).toMatchObject({ description, target: { level: target.level, tooth: "UR6", surfaces: target.surfaces }, fee_mode: "agreed", fee_pence: 2125 });
    expect(payload).not.toHaveProperty("treatment_id"); expect(payload).not.toHaveProperty("quote_token");
    const saved = await response.json(); expect(saved).toMatchObject({ description, treatment_id: null, catalogue_snapshot: { source: "custom" }, drawing_kind: "other", target: { level: target.level, tooth: "UR6", surfaces: target.surfaces }, procedure_code: "MISCELLANEOUS", completed_procedure_id: null });
    await expect(page.getByTestId("planning-treatment-dialog")).toBeHidden(); await expect(page.getByTestId(`planning-item-${saved.id}`)).toContainText(description);
  }
  await expect(page.getByTestId("planning-total-outstanding")).toHaveText("£85.00");
  const after = await request.get(`${endpoint}/clinical/tooth-conditions`, { headers }); expect(await after.json()).toEqual(baseline);
  const ledger = await request.get(`${endpoint}/ledger`, { headers }); expect(ledger.ok()).toBeTruthy(); expect(await ledger.json()).toEqual([]);
  const planning = await request.get(`${endpoint}/planning`, { headers }); const items = (await planning.json()).plan.items;
  expect(items).toHaveLength(4); expect(items.map((item: { target: { level: string } }) => item.target.level)).toEqual(expect.arrayContaining(["tooth", "root", "crown", "surface"]));
});

async function mockPracticeCatalogue(page: Page, request: APIRequestContext, withSavedLegacyItem = false) {
  const { id } = await fixture(page, request), queries: URLSearchParams[] = [];
  const writes: { path: string; method: string; body: Record<string, unknown> }[] = [];
  const entry = (id: number, name: string, level: PlanningCatalogueItem["level"]): PlanningCatalogueItem => ({ id, name, level, display_order: id, code: `SYN${id}`, description: "Synthetic catalogue fixture", default_duration_minutes: 30, patient_category: "CLINIC_PRIVATE", fee: { type: "FIXED", amount_pence: 12500, min_amount_pence: null, max_amount_pence: null, notes: null }, quote_token: String(id).repeat(64).slice(0, 64) });
  // More than one page of legacy rows proves filtering must precede totals/paging.
  const legacy = Array.from({ length: 60 }, (_, index) => entry(1000 + index, `Simple old demo ${index}`, null));
  const routines = [entry(1, "Simple extraction", "tooth"), entry(2, "Sample root treatment", "root"), entry(3, "Sample crown treatment", "crown"), entry(4, "Sample surface treatment", "surface"), entry(5, "Sample general treatment", "general")];
  routines[0].fee = { type: "UNAVAILABLE", amount_pence: null, min_amount_pence: null, max_amount_pence: null, notes: null };
  const entries = [...legacy, ...routines];
  const items: PlanningItem[] = withSavedLegacyItem ? [{ id: 90, patient_id: Number(id), plan_id: 10, treatment_id: legacy[0].id, revision: 1, tooth: "UR6", surface: null, target: { level: "root", tooth: "UR6", surfaces: [] }, drawing_kind: "other", procedure_code: legacy[0].code!, description: "Saved legacy proposal", fee_pence: 12500, fee_mode: "catalogue", fee_reason: null, status: "proposed", catalogue_snapshot: structuredClone(legacy[0]), completed_procedure_id: null, created_at: "2030-01-07T09:00:00Z", updated_at: "2030-01-07T09:00:00Z" }] : [];
  const state: PlanningResponse = { patient_id: Number(id), plan: { id: 10, created_at: "2030-01-07T09:00:00Z", created_by: null, snapshot: { version: 1, captured_at: "2030-01-07T09:00:00Z", native: { patient_id: Number(id), teeth: {}, note_teeth: [], bridges: [] }, legacy: null, coverage: { native: "captured", legacy: "unavailable", legacy_reason: "No imported chart linked" } }, items }, earlier_items: [], earlier_items_total: 0 };
  await page.route(`**/api/patients/${id}/planning**`, async (route) => {
    const req = route.request(), url = new URL(req.url());
    if (req.method() !== "GET") {
      const body = req.postDataJSON(); writes.push({ path: url.pathname, method: req.method(), body });
      if (withSavedLegacyItem && req.method() === "PATCH" && url.pathname.endsWith("/items/90")) {
        const saved = state.plan!.items[0];
        if (body.expected_revision !== saved.revision) { await route.fulfill({ status: 409, json: { detail: "Synthetic revision conflict" } }); return; }
        saved.fee_mode = body.fee_mode; saved.fee_pence = body.fee_pence; saved.fee_reason = body.fee_reason; saved.revision += 1;
        await route.fulfill({ json: saved }); return;
      }
      await route.fulfill({ status: 500, json: { detail: "This inspection test must not write" } }); return;
    }
    if (url.pathname.endsWith("/catalogue")) {
      queries.push(url.searchParams);
      const level = url.searchParams.get("level"), includeUnassigned = url.searchParams.get("include_unassigned") !== "false", classifiedOnly = url.searchParams.get("classified_only") === "true", search = (url.searchParams.get("q") ?? "").toLowerCase();
      const matching = entries.filter((item) => (!classifiedOnly || item.level != null) && (!level || item.level === level || (item.level == null && includeUnassigned)) && `${item.name} ${item.code}`.toLowerCase().includes(search));
      const offset = Number(url.searchParams.get("offset") ?? 0), limit = Number(url.searchParams.get("limit") ?? 50);
      await route.fulfill({ json: { patient_id: Number(id), patient_category: "CLINIC_PRIVATE", currency: "GBP", practice_today: "2030-01-07", items: matching.slice(offset, offset + limit), total: matching.length } }); return;
    }
    await route.fulfill({ json: state });
  });
  return { id, entries, legacy, queries, writes, state };
}

test("all five practice levels are the picker default and search finds an unpriced routine without legacy demos", async ({ page, request }) => {
  const harness = await mockPracticeCatalogue(page, request), originalLegacy = structuredClone(harness.legacy);
  await open(page, harness.id); await page.getByTestId("clinical-crown-UR6").click();
  await expect(page.getByTestId("planning-catalogue-scope")).toHaveValue("all");
  await expect(page.getByTestId("planning-catalogue-scope").locator('option:checked')).toHaveText("All practice levels");
  await expect(page.locator('[data-testid^="planning-catalogue-item-"]')).toHaveCount(5);
  expect(harness.queries.at(-1)!.has("level")).toBeFalsy();
  await expect(page.getByRole("button", { name: "Next treatments", exact: true })).toHaveCount(0);
  await expect(page.getByTestId("planning-catalogue")).not.toContainText("old demo");
  await page.getByTestId("planning-catalogue-scope").selectOption("target");
  await expect(page.locator('[data-testid^="planning-catalogue-item-"]')).toHaveCount(1); await expect(page.getByTestId("planning-catalogue-item-3")).toBeVisible();
  expect(harness.queries.at(-1)!.get("level")).toBe("crown");
  await page.getByTestId("planning-catalogue-scope").selectOption("all"); await page.getByTestId("planning-catalogue-search").fill("sim");
  await expect(page.locator('[data-testid^="planning-catalogue-item-"]')).toHaveCount(1);
  await expect(page.getByTestId("planning-catalogue-item-1")).toContainText("Simple extraction");
  await expect(page.getByTestId("planning-catalogue-item-1")).toContainText("No catalogue fee recorded"); await expect(page.getByTestId("planning-catalogue-item-1")).not.toContainText("£0.00");
  await expect(page.getByTestId("planning-target-level")).toHaveValue("crown"); await expect(page.getByTestId("planning-target-tooth")).toHaveValue("UR6");
  const previews = path.join(process.cwd(), ".run", "planning-practice-picker-previews"); await mkdir(previews, { recursive: true });
  for (const theme of ["light", "dark"]) {
    await page.evaluate((value) => document.documentElement.dataset.theme = value, theme);
    await page.getByTestId("planning-treatment-dialog").screenshot({ path: path.join(previews, `${theme}-practice-picker.png`) });
  }
  await page.setViewportSize({ width: 390, height: 844 }); await page.getByTestId("planning-cancel").scrollIntoViewIfNeeded();
  const dialogBounds = (await page.getByTestId("planning-treatment-dialog").boundingBox())!;
  expect(dialogBounds.x).toBeGreaterThanOrEqual(0); expect(dialogBounds.x + dialogBounds.width).toBeLessThanOrEqual(390);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  await page.screenshot({ path: path.join(previews, "mobile-practice-picker.png") });
  await page.getByTestId("planning-cancel").click(); await page.setViewportSize({ width: 1600, height: 1100 });
  await page.getByTestId("clinical-root-UR6").click(); await expect(page.getByTestId("planning-catalogue-scope")).toHaveValue("all");
  await expect(page.locator('[data-testid^="planning-catalogue-item-"]')).toHaveCount(5);
  await page.getByTestId("planning-other-treatment").click(); await page.getByTestId("planning-other-description").fill("Unsaved custom root description"); await page.getByTestId("planning-use-catalogue").click();
  await expect(page.getByTestId("planning-target-level")).toHaveValue("root"); await expect(page.getByTestId("planning-target-tooth")).toHaveValue("UR6");
  await expect(page.getByTestId("planning-catalogue")).not.toContainText("old demo"); await page.getByTestId("planning-cancel").click();
  for (const query of harness.queries) { expect(query.get("classified_only")).toBe("true"); expect(query.get("include_unassigned")).toBe("false"); }
  expect(harness.writes).toEqual([]); expect(harness.legacy).toEqual(originalLegacy);
});

test("a differently classified routine requires explicit level choice and never invents a target drawing or fee", async ({ page, request }) => {
  const harness = await mockPracticeCatalogue(page, request); await open(page, harness.id); await page.getByTestId("clinical-crown-UR6").click();
  await page.getByTestId("planning-drawing-kind").selectOption("crown"); await page.getByTestId("planning-catalogue-item-1").click();
  await expect(page.getByTestId("planning-target-level")).toHaveValue("crown"); await expect(page.getByTestId("planning-target-tooth")).toHaveValue("UR6");
  await expect(page.getByTestId("planning-use-treatment-level")).toHaveText("Use Tooth level"); await expect(page.getByTestId("planning-save")).toBeDisabled();
  await page.getByTestId("planning-use-treatment-level").focus(); await page.keyboard.press("Enter");
  await expect(page.getByTestId("planning-target-level")).toHaveValue("tooth"); await expect(page.getByTestId("planning-target-tooth")).toHaveValue("UR6");
  await expect(page.getByTestId("planning-drawing-kind")).toHaveValue(""); await expect(page.getByTestId("planning-fee-mode")).toHaveValue("agreed");
  await expect(page.getByTestId("planning-fee-amount")).toHaveValue(""); await expect(page.getByTestId("planning-save")).toBeDisabled();
  await page.getByTestId("planning-drawing-kind").selectOption("extraction"); await page.getByTestId("planning-fee-amount").fill("25");
  await expect(page.getByTestId("planning-save")).toBeDisabled(); await page.getByTestId("planning-fee-reason").fill("Synthetic agreed fee; routine has no practice price yet");
  await expect(page.getByTestId("planning-save")).toBeEnabled(); await page.getByTestId("planning-cancel").click();
  await page.getByTestId("clinical-surface-UR6-M").click(); await expect(page.getByTestId("planning-target-surface-M")).toBeChecked();
  await page.getByTestId("planning-drawing-kind").selectOption("filling"); await page.getByTestId("planning-catalogue-item-1").click(); await page.getByTestId("planning-use-treatment-level").click();
  await expect(page.getByTestId("planning-target-level")).toHaveValue("tooth"); await expect(page.getByTestId("planning-drawing-kind")).toHaveValue("");
  await page.getByTestId("planning-target-level").selectOption("surface"); await expect(page.getByTestId("planning-target-surface-M")).not.toBeChecked();
  await page.getByTestId("planning-target-surface-M").check(); await page.getByTestId("planning-catalogue-item-5").click();
  await expect(page.getByTestId("planning-target-level")).toHaveValue("surface"); await expect(page.getByTestId("planning-use-treatment-level")).toHaveText("Use General treatment");
  await page.getByTestId("planning-use-treatment-level").click(); await expect(page.getByTestId("planning-target-level")).toHaveValue("general");
  await expect(page.getByTestId("planning-target-tooth")).toHaveCount(0); await expect(page.getByRole("group", { name: "Treatment surfaces", exact: true })).toHaveCount(0);
  await page.getByTestId("planning-cancel").click(); expect(harness.writes).toEqual([]);
});

test("saved unassigned catalogue proposals retain their captured quote and remain fee editable while hidden from new picks", async ({ page, request }) => {
  const harness = await mockPracticeCatalogue(page, request, true), originalQuote = structuredClone(harness.state.plan!.items[0].catalogue_snapshot);
  await open(page, harness.id); await page.getByTestId("planning-item-90").click(); await page.getByTestId("planning-action-edit-fee").click();
  await expect(page.getByTestId("planning-treatment-dialog")).toContainText("Saved legacy proposal"); await expect(page.getByTestId("planning-fee-quote")).toContainText("£125.00");
  await expect(page.getByTestId("planning-catalogue")).toHaveCount(0); expect(harness.queries).toHaveLength(0);
  await page.getByTestId("planning-fee-mode").selectOption("override"); await page.getByTestId("planning-fee-amount").fill("90");
  await page.getByTestId("planning-fee-reason").fill("Synthetic revised patient quote"); await page.getByTestId("planning-save").click();
  await expect(page.getByTestId("planning-treatment-dialog")).toBeHidden(); await expect(page.getByTestId("planning-item-90")).toContainText("£90.00");
  expect(harness.writes).toEqual([{ method: "PATCH", path: `/api/patients/${harness.id}/planning/items/90`, body: { expected_revision: 1, fee_mode: "override", fee_pence: 9000, fee_reason: "Synthetic revised patient quote" } }]);
  expect(harness.state.plan!.items[0].catalogue_snapshot).toEqual(originalQuote);
  await page.reload({ waitUntil: "domcontentloaded" }); await expect(page.getByTestId("planning-item-90")).toBeVisible({ timeout: 30_000 });
  await page.getByTestId("planning-item-90").click(); await page.getByTestId("planning-action-edit-fee").click();
  await expect(page.getByTestId("planning-fee-amount")).toHaveValue("90.00"); await expect(page.getByTestId("planning-fee-quote")).toContainText("£125.00"); await page.getByTestId("planning-cancel").click();
  await page.getByTestId("clinical-root-UR6").click(); await expect(page.locator('[data-testid^="planning-catalogue-item-"]')).toHaveCount(5);
  await expect(page.getByTestId(`planning-catalogue-item-${harness.legacy[0].id}`)).toHaveCount(0); await page.getByTestId("planning-cancel").click();
  expect(harness.writes).toHaveLength(1); expect(harness.state.plan!.items[0].catalogue_snapshot).toEqual(originalQuote);
});
