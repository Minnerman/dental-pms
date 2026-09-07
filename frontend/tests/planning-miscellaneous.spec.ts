import { expect, test, type APIRequestContext, type Page, type Route } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

type CustomItem = {
  id: number; patient_id: number; plan_id: number; treatment_id: null; revision: number;
  tooth: null; surface: null; target: { level: "general"; tooth: null; surfaces: [] };
  drawing_kind: "other"; procedure_code: "MISCELLANEOUS"; description: string;
  fee_pence: number; fee_mode: "agreed" | "waived"; fee_reason: string | null;
  catalogue_snapshot: { source: "custom" }; status: "proposed" | "accepted" | "completed" | "cancelled";
  completed_procedure_id: number | null; created_at: string; updated_at: string;
};
type Write = { path: string; method: string; body: Record<string, unknown>; requestId: string | undefined };

async function fixture(page: Page, request: APIRequestContext) {
  const token = await primePageAuth(page, request);
  const id = await createPatient(request, { first_name: "Synthetic", last_name: `Miscellaneous planning ${Date.now()}` });
  await page.setViewportSize({ width: 1600, height: 1100 });
  return { id, headers: { Authorization: `Bearer ${token}` } };
}

function customItem(patientId: string, id: number, patch: Partial<CustomItem> = {}): CustomItem {
  return { id, patient_id: Number(patientId), plan_id: 10, treatment_id: null, revision: 1,
    tooth: null, surface: null, target: { level: "general", tooth: null, surfaces: [] }, drawing_kind: "other",
    procedure_code: "MISCELLANEOUS", description: "Synthetic custom treatment", fee_pence: 3750,
    fee_mode: "agreed", fee_reason: null, catalogue_snapshot: { source: "custom" }, status: "proposed",
    completed_procedure_id: null, created_at: "2026-09-07T09:00:00Z", updated_at: "2026-09-07T09:00:00Z", ...patch };
}

async function mocked(page: Page, request: APIRequestContext) {
  const { id, headers } = await fixture(page, request);
  const state = { patient_id: Number(id), plan: { id: 10, created_at: "2026-09-07T09:00:00Z", created_by: null,
    snapshot: { version: 1, captured_at: "2026-09-07T09:00:00Z", native: { patient_id: Number(id), teeth: {}, note_teeth: [], bridges: [] }, legacy: null,
      coverage: { native: "captured", legacy: "unavailable", legacy_reason: "No imported chart linked to this synthetic patient." } }, items: [] as CustomItem[] }, earlier_items: [], earlier_items_total: 0 };
  const harness = { id, headers, state, failReads: false, writes: [] as Write[], intercept: null as ((route: Route, write: Write) => Promise<boolean>) | null };
  await page.route(`**/api/patients/${id}/planning**`, async (route) => {
    const req = route.request(), url = new URL(req.url());
    if (req.method() === "GET") {
      if (harness.failReads) { await route.fulfill({ status: 503, json: { detail: "Synthetic plan refresh unavailable" } }); return; }
      await route.fulfill({ json: url.pathname.endsWith("/catalogue") ? { patient_id: Number(id), patient_category: "CLINIC_PRIVATE", currency: "GBP", items: [], total: 0 } : state }); return;
    }
    const write: Write = { path: url.pathname, method: req.method(), body: req.postDataJSON(), requestId: req.headers()["request-id"] };
    harness.writes.push(write);
    if (harness.intercept && await harness.intercept(route, write)) return;
    if (url.pathname.endsWith("/custom-items")) {
      const item = customItem(id, 100 + state.plan.items.length, { description: String(write.body.description), fee_pence: Number(write.body.fee_pence), fee_mode: write.body.fee_mode as CustomItem["fee_mode"], fee_reason: (write.body.fee_reason as string | null) ?? null });
      state.plan.items.push(item); await route.fulfill({ status: 201, json: item }); return;
    }
    const item = state.plan.items.find((value) => value.id === Number(url.pathname.split("/").at(-1)));
    if (!item || item.revision !== write.body.expected_revision) { await route.fulfill({ status: 409, json: { detail: "Synthetic revision conflict" } }); return; }
    if (write.body.fee_mode) Object.assign(item, { fee_mode: write.body.fee_mode, fee_pence: write.body.fee_pence, fee_reason: write.body.fee_reason ?? null });
    if (write.body.status) item.status = write.body.status as CustomItem["status"];
    item.revision += 1; await route.fulfill({ json: item });
  });
  return harness;
}

async function open(page: Page, id: string) {
  await page.goto(`${getBaseUrl()}/patients/${id}/clinical?clinicalView=planned`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("treatment-planning-panel")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("planning-loading")).toHaveCount(0, { timeout: 30_000 });
}
async function misc(page: Page) {
  await page.getByTestId("planning-level-general").click();
  await expect(page.getByTestId("planning-level-general")).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId("planning-miscellaneous")).toBeVisible();
  await expect(page.getByTestId("treatment-planning-chart")).toHaveCount(0);
}
async function select(page: Page, id: number) {
  await page.getByTestId(`planning-item-${id}`).click();
  await expect(page.getByTestId("planning-selected-item")).toHaveAttribute("data-item-id", String(id));
}

test("real miscellaneous treatment proposes without a charge then edits completes and uncompletes with preserved history", async ({ page, request }) => {
  const { id, headers } = await fixture(page, request), endpoint = `${getBaseUrl()}/api/patients/${id}`;
  const diagnosis = await request.post(`${endpoint}/clinical/tooth-conditions`, { headers, data: { teeth: ["UR4"], condition: "missing", expected_revisions: { UR4: 0 } } });
  expect(diagnosis.ok()).toBeTruthy(); const baseline = await diagnosis.json();
  const writes: string[] = []; page.on("request", (req) => { if (["POST", "PATCH", "PUT", "DELETE"].includes(req.method())) writes.push(new URL(req.url()).pathname); });
  await open(page, id); await page.getByTestId("planning-start").click(); await expect(page.getByTestId("treatment-planning-chart")).toBeVisible(); await misc(page);
  const description = `Synthetic custom appointment ${id}\nAdditional non-tooth treatment entered by the clinician.`;
  await page.getByTestId("planning-custom-description").fill(description); await page.getByTestId("planning-custom-fee-amount").fill("37.50");
  const createResponse = page.waitForResponse((response) => response.request().method() === "POST" && response.url().endsWith(`/api/patients/${id}/planning/custom-items`));
  await page.getByTestId("planning-custom-save").click(); const created = await createResponse; expect(created.ok()).toBeTruthy();
  expect(created.request().postDataJSON()).toMatchObject({ description, fee_pence: 3750, fee_mode: "agreed" });
  const item = await created.json() as CustomItem;
  expect(item).toMatchObject({ treatment_id: null, target: { level: "general", tooth: null, surfaces: [] }, drawing_kind: "other", procedure_code: "MISCELLANEOUS", fee_pence: 3750, fee_mode: "agreed", status: "proposed", completed_procedure_id: null, catalogue_snapshot: { source: "custom" } });
  expect(item.catalogue_snapshot).toEqual({ source: "custom" });
  await expect(page.getByTestId(`planning-item-${item.id}`)).toContainText("£37.50"); await expect(page.getByTestId("planning-total-outstanding")).toHaveText("£37.50");
  const ledgerBefore = await request.get(`${endpoint}/ledger`, { headers }); expect(ledgerBefore.ok()).toBeTruthy(); expect(await ledgerBefore.json()).toEqual([]);
  const summaryBefore = await request.get(`${endpoint}/clinical/summary?limit=200`, { headers }); expect((await summaryBefore.json()).recent_procedures).toEqual([]);
  const catalogue = await request.get(`${endpoint}/planning/catalogue?${new URLSearchParams({ q: `Synthetic custom appointment ${id}` })}`, { headers }); expect(catalogue.ok()).toBeTruthy(); expect((await catalogue.json()).items).toEqual([]);
  await page.reload({ waitUntil: "domcontentloaded" }); await expect(page.getByTestId(`planning-item-${item.id}`)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("tooth-svg-UR4")).toHaveAttribute("data-baseline-status", "missing");
  await expect(page.locator('[data-testid^="tooth-planning-overlay-"]')).toHaveCount(0);
  await select(page, item.id); await page.getByTestId("planning-action-details").click();
  await expect(page.getByTestId("planning-item-details")).toContainText(description);
  await expect(page.getByTestId("planning-item-details")).not.toContainText("Saved catalogue quote");
  await page.getByRole("button", { name: "Close treatment details", exact: true }).click();
  await page.getByTestId("planning-action-edit-fee").click(); await expect(page.getByTestId("planning-fee-mode").locator('option[value="catalogue"]')).toHaveCount(0);
  await page.getByTestId("planning-fee-amount").fill("42.25");
  await page.getByTestId("planning-fee-reason").fill("Synthetic agreed fee revision");
  await page.getByTestId("planning-save").click(); await expect(page.getByTestId("planning-treatment-dialog")).toBeHidden();
  await expect(page.getByTestId(`planning-item-${item.id}`)).toContainText("£42.25");
  const noChargeAfterEdit = await request.get(`${endpoint}/ledger`, { headers }); expect(await noChargeAfterEdit.json()).toEqual([]);
  await select(page, item.id); page.once("dialog", (dialog) => dialog.accept()); await page.getByTestId("planning-action-accept").click(); await expect(page.getByTestId(`planning-item-${item.id}`)).toHaveAttribute("data-status", "accepted");
  let completionText = ""; page.once("dialog", async (dialog) => { completionText = dialog.message(); await dialog.accept(); }); await page.getByTestId("planning-action-complete").click();
  await expect(page.getByTestId(`planning-item-${item.id}`)).toHaveAttribute("data-status", "completed"); expect(completionText).toContain("£42.25");
  const completedLedger = await request.get(`${endpoint}/ledger`, { headers }); const charges = await completedLedger.json();
  expect(charges).toHaveLength(1); expect(charges[0]).toMatchObject({ entry_type: "charge", amount_pence: 4225, reference: `TREATMENT-PLAN:${item.id}` });
  const completedSummary = await request.get(`${endpoint}/clinical/summary?limit=200`, { headers }); const procedures = (await completedSummary.json()).recent_procedures;
  expect(procedures).toHaveLength(1); expect(procedures[0]).toMatchObject({ description, procedure_code: "MISCELLANEOUS", tooth: null, surface: null, fee_pence: 4225 });
  await page.getByTestId("planning-action-uncomplete").click(); await page.getByTestId("planning-uncomplete-reason").fill("Synthetic accidental completion correction"); await page.getByTestId("planning-uncomplete-confirm").click();
  await expect(page.getByTestId(`planning-item-${item.id}`)).toHaveAttribute("data-status", "accepted");
  await expect(page.getByTestId("planning-total-outstanding")).toHaveText("£42.25"); await expect(page.getByTestId("planning-total-completed")).toHaveText("£0.00");
  const reversedLedger = await request.get(`${endpoint}/ledger`, { headers }); const entries = await reversedLedger.json() as { entry_type: string; amount_pence: number; reference: string }[];
  expect(entries).toHaveLength(2); expect(entries.reduce((sum, entry) => sum + entry.amount_pence, 0)).toBe(0);
  expect(entries.find((entry) => entry.entry_type === "adjustment")).toMatchObject({ amount_pence: -4225, reference: `TREATMENT-PLAN:${item.id}:C1:REVERSAL` });
  const history = await request.get(`${endpoint}/planning/items/${item.id}/history`, { headers }); const versions = (await history.json()).items;
  expect(versions.find((version: { revision: number }) => version.revision === 1).snapshot).toMatchObject({ description, fee_pence: 3750, catalogue_snapshot: { source: "custom" } });
  expect(versions.find((version: { revision: number }) => version.revision === 2).snapshot).toMatchObject({ description, fee_pence: 4225, fee_reason: "Synthetic agreed fee revision" });
  const afterDiagnosis = await request.get(`${endpoint}/clinical/tooth-conditions`, { headers }); expect(await afterDiagnosis.json()).toEqual(baseline);
  expect(writes.every((url) => url.startsWith(`/api/patients/${id}/planning`))).toBeTruthy();
});

test("miscellaneous requires a description and explicit valid fee or a reasoned zero waiver", async ({ page, request }) => {
  const harness = await mocked(page, request); await open(page, harness.id); await misc(page);
  const save = page.getByTestId("planning-custom-save"), description = page.getByTestId("planning-custom-description"), fee = page.getByTestId("planning-custom-fee-amount");
  await expect(description).toHaveValue(""); await expect(description).toHaveAttribute("maxlength", "2000"); await expect(fee).toHaveValue(""); await expect(save).toBeDisabled();
  await description.fill("   "); await fee.fill("15"); await expect(save).toBeDisabled();
  await description.fill("Synthetic explicit-price treatment");
  for (const value of ["", "0", "-1", "1.001", "1000000.01"]) { await fee.fill(value); await expect(save).toBeDisabled(); }
  await fee.fill("15.25"); await expect(save).toBeEnabled(); expect(harness.writes).toEqual([]);
  await page.getByTestId("planning-custom-waived").check(); await expect(save).toBeDisabled();
  await page.getByTestId("planning-custom-fee-reason").fill("   "); await expect(save).toBeDisabled();
  await page.getByTestId("planning-custom-fee-reason").fill("Synthetic explicit fee waiver"); await expect(save).toBeEnabled();
  await save.click(); await expect(page.getByTestId("planning-item-100")).toBeVisible();
  expect(harness.writes).toHaveLength(1); expect(harness.writes[0].body).toMatchObject({ description: "Synthetic explicit-price treatment", fee_mode: "waived", fee_pence: 0, fee_reason: "Synthetic explicit fee waiver" });
  await select(page, 100); await page.getByTestId("planning-action-details").click(); await expect(page.getByTestId("planning-item-details")).toContainText("£0.00"); await expect(page.getByTestId("planning-item-details")).toContainText("Synthetic explicit fee waiver");
});

test("pending and uncertain miscellaneous saves lock the draft and reuse one unchanged request identity", async ({ page, request }) => {
  const harness = await mocked(page, request); await open(page, harness.id); await misc(page);
  await page.getByTestId("planning-custom-description").fill("Synthetic single pending custom treatment"); await page.getByTestId("planning-custom-fee-amount").fill("25.50");
  let release!: () => void; const gate = new Promise<void>((resolve) => { release = resolve; }); let failures = 0;
  harness.intercept = async (route, write) => {
    if (!write.path.endsWith("/custom-items")) return false;
    if (failures++ === 0) { await gate; await route.fulfill({ status: 503, json: { detail: "Synthetic uncertain save" } }); return true; }
    if (failures === 2) { await route.fulfill({ status: 409, json: { detail: "Synthetic retry conflict does not settle the original unknown result" } }); return true; }
    return false;
  };
  try {
    await page.getByTestId("planning-custom-save").evaluate((button) => { (button as HTMLButtonElement).click(); (button as HTMLButtonElement).click(); });
    await expect(page.getByTestId("planning-custom-progress")).toBeVisible();
    await expect(page.getByTestId("planning-custom-save")).toBeDisabled(); await expect(page.getByTestId("planning-custom-description")).toBeDisabled(); await expect(page.getByTestId("planning-custom-fee-amount")).toBeDisabled(); await expect(page.getByTestId("planning-custom-waived")).toBeDisabled();
    for (const level of ["tooth", "root", "crown", "surface", "general"]) await expect(page.getByTestId(`planning-level-${level}`)).toBeDisabled();
    await expect(page.getByTestId("planning-add-treatment")).toBeDisabled(); await expect(page.getByTestId("planning-action-complete")).toBeDisabled();
    await page.keyboard.press("Control+1"); await page.keyboard.press("Meta+1"); await page.keyboard.press("Escape");
    await expect(page.getByTestId("planning-custom-progress")).toBeVisible(); await expect(page.getByTestId("patient-tab-Medical")).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("clinical-chart-view-planned")).toHaveAttribute("aria-pressed", "true");
    expect(harness.writes).toHaveLength(1); expect(harness.state.plan.items).toHaveLength(0);
  } finally { release(); }
  await expect(page.getByTestId("planning-custom-progress").getByRole("alert")).toContainText(/could not be confirmed|unknown/i);
  await expect(page.getByTestId("planning-custom-description")).toBeDisabled(); await expect(page.getByTestId("planning-level-tooth")).toBeDisabled();
  await page.getByTestId("planning-custom-retry").click();
  await expect(page.getByTestId("planning-custom-progress").getByRole("alert")).toContainText(/could not be confirmed|unknown|unconfirmed/i);
  await expect(page.getByTestId("planning-custom-progress")).toBeVisible(); await expect(page.getByTestId("planning-custom-description")).toBeDisabled();
  expect(harness.writes).toHaveLength(2); expect(harness.state.plan.items).toHaveLength(0);
  await page.getByTestId("planning-custom-retry").click(); await expect(page.getByTestId("planning-item-100")).toBeVisible(); await expect(page.getByTestId("planning-custom-progress")).toBeHidden();
  expect(harness.writes).toHaveLength(3); expect(harness.writes[0].requestId).toBeTruthy(); expect(harness.writes[1]).toEqual(harness.writes[0]); expect(harness.writes[2]).toEqual(harness.writes[0]); expect(harness.state.plan.items).toHaveLength(1);
});

test("an unknown custom save can be abandoned after failed review without allowing another unchecked submission", async ({ page, request }) => {
  const harness = await mocked(page, request); await open(page, harness.id); await misc(page);
  await page.getByTestId("planning-custom-description").fill("Synthetic unconfirmed treatment to review"); await page.getByTestId("planning-custom-fee-amount").fill("22.50");
  harness.intercept = async (route) => { await route.fulfill({ status: 503, json: { detail: "Synthetic unknown save" } }); return true; };
  await page.getByTestId("planning-custom-save").click();
  const progress = page.getByTestId("planning-custom-progress"); await expect(progress.getByRole("alert")).toContainText(/could not be confirmed|unknown/i);
  harness.failReads = true; let reviewWarning = "";
  page.once("dialog", async (dialog) => { reviewWarning = dialog.message(); await dialog.accept(); }); await page.getByTestId("planning-custom-review").click();
  await expect(page.getByTestId("planning-custom-abandon")).toBeVisible(); expect(reviewWarning).toContain("may already have been added");
  await expect(progress).toBeVisible(); await expect(page.getByTestId("planning-custom-retry")).toBeDisabled();
  let abandonWarning = ""; page.once("dialog", async (dialog) => { abandonWarning = dialog.message(); await dialog.accept(); }); await page.getByTestId("planning-custom-abandon").click();
  await expect(progress).toBeHidden(); expect(abandonWarning).toMatch(/still unknown.*could not be refreshed/);
  await expect(page.getByTestId("planning-custom-description")).toHaveValue(""); await expect(page.getByTestId("planning-custom-fee-amount")).toHaveValue("");
  await expect(page.getByTestId("planning-custom-description")).toBeDisabled(); await expect(page.getByTestId("planning-custom-save")).toBeDisabled(); await expect(page.getByTestId("planning-add-treatment")).toBeDisabled();
  expect(harness.writes).toHaveLength(1); expect(harness.state.plan.items).toHaveLength(0);
});

test("read-only miscellaneous remains inspectable and completion still requires billing permission", async ({ page, request }) => {
  const harness = await mocked(page, request); harness.state.plan.items = [customItem(harness.id, 100), customItem(harness.id, 101, { status: "completed", completed_procedure_id: 500 })];
  await page.route("**/api/me/capabilities", (route) => route.fulfill({ json: ["patients.view", "clinical.view", "notes.view"] }));
  await open(page, harness.id); await misc(page);
  for (const field of ["description", "fee-amount", "waived", "save"]) await expect(page.getByTestId(`planning-custom-${field}`)).toBeDisabled();
  await select(page, 100); await expect(page.getByTestId("planning-action-details")).toBeEnabled(); await expect(page.getByTestId("planning-action-edit-fee")).toBeDisabled(); await expect(page.getByTestId("planning-action-complete")).toBeDisabled();
  await select(page, 101); await expect(page.getByTestId("planning-action-uncomplete")).toBeDisabled();
  await page.unroute("**/api/me/capabilities"); await page.route("**/api/me/capabilities", (route) => route.fulfill({ json: ["patients.view", "clinical.view", "clinical.write", "notes.view"] }));
  await page.reload({ waitUntil: "domcontentloaded" }); await expect(page.getByTestId("planning-item-100")).toBeVisible({ timeout: 30_000 }); await misc(page);
  await expect(page.getByTestId("planning-custom-description")).toBeEnabled(); await select(page, 100); await expect(page.getByTestId("planning-action-edit-fee")).toBeEnabled(); await expect(page.getByTestId("planning-action-complete")).toBeDisabled();
  await select(page, 101); await expect(page.getByTestId("planning-action-uncomplete")).toBeDisabled(); expect(harness.writes).toEqual([]);
});

test("five planning tabs retain miscellaneous drafts with keyboard navigation and fit light dark and mobile", async ({ page, request }) => {
  const harness = await mocked(page, request); harness.state.plan.items = [customItem(harness.id, 100), customItem(harness.id, 101, { description: "Synthetic completed miscellaneous treatment", status: "completed", completed_procedure_id: 501 })];
  await open(page, harness.id);
  const tabs = page.getByRole("tablist", { name: "Planning level", exact: true }); await expect(tabs.getByRole("tab")).toHaveCount(5); await expect(tabs.getByText("Planning:", { exact: true })).toHaveCount(0);
  await page.getByTestId("planning-level-tooth").focus(); await page.keyboard.press("End"); await expect(page.getByTestId("planning-level-general")).toBeFocused(); await expect(page.getByTestId("planning-miscellaneous")).toBeVisible();
  await page.getByTestId("planning-custom-description").fill("Synthetic miscellaneous draft retained while choosing a different planning category"); await page.getByTestId("planning-custom-fee-amount").fill("18.75");
  await page.getByTestId("planning-level-general").focus(); await page.keyboard.press("ArrowRight"); await expect(page.getByTestId("planning-level-tooth")).toBeFocused(); await expect(page.getByTestId("treatment-planning-chart")).toBeVisible();
  await page.keyboard.press("ArrowLeft"); await expect(page.getByTestId("planning-level-general")).toBeFocused(); await expect(page.getByTestId("planning-custom-fee-amount")).toHaveValue("18.75");
  await expect(page.getByTestId("planning-custom-description")).toHaveValue("Synthetic miscellaneous draft retained while choosing a different planning category");
  await page.keyboard.press("Home"); await expect(page.getByTestId("planning-level-tooth")).toBeFocused(); await page.keyboard.press("End");
  await select(page, 100); const previews = path.join(process.cwd(), ".run", "planning-miscellaneous-previews"); await mkdir(previews, { recursive: true });
  for (const theme of ["light", "dark"]) {
    await page.evaluate((value) => document.documentElement.dataset.theme = value, theme); await page.evaluate(() => scrollTo(0, 0));
    await page.screenshot({ path: path.join(previews, `${theme}-miscellaneous.png`), fullPage: true });
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByTestId("planning-custom-save").scrollIntoViewIfNeeded(); const save = (await page.getByTestId("planning-custom-save").boundingBox())!;
  expect(save.x).toBeGreaterThanOrEqual(0); expect(save.x + save.width).toBeLessThanOrEqual(390);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  await page.evaluate(() => scrollTo(0, 0)); await page.screenshot({ path: path.join(previews, "mobile-miscellaneous.png"), fullPage: true }); expect(harness.writes).toEqual([]);
});
