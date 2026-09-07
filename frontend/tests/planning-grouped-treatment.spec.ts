import { expect, test, type APIRequestContext, type Page, type Route } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";
import type { PlanningCatalogueItem, PlanningDrawingKind, PlanningFee, PlanningItem, PlanningMaterial, PlanningResponse, PlanningSnapshot } from "../components/clinical/treatmentPlanning";

type Defaults = { drawing_kind: PlanningDrawingKind; material: PlanningMaterial | null };
type Member = { tooth: string; role: "abutment" | "pontic" | "wing" | "denture" };
type Appliance = { kind: "bridge" | "denture"; arch: "upper" | "lower"; members: Member[] };
type Entry = PlanningCatalogueItem & { planning_defaults: Defaults | null; planning_defaults_revision: number; suggested_planning_defaults: Defaults | null; routine_key: string | null };
type Item = PlanningItem & { appliance?: Appliance | null; pricing?: { basis: "per_unit" | "appliance"; quantity: number; unit_fee_pence: number | null; total_fee_pence: number } };
type Fixture = { id: string; endpoint: string; headers: Record<string, string> };
type Write = { method: string; body: Record<string, unknown>; requestId: string | undefined; path: string };
const bridge: Appliance = { kind: "bridge", arch: "upper", members: [{ tooth: "UL6", role: "abutment" }, { tooth: "UL7", role: "pontic" }, { tooth: "UL8", role: "abutment" }] };
const denture: Appliance = { kind: "denture", arch: "lower", members: [{ tooth: "LR5", role: "denture" }, { tooth: "LL4", role: "denture" }, { tooth: "LL6", role: "denture" }] };
const unit: PlanningFee = { type: "FIXED", amount_pence: 12300, min_amount_pence: null, max_amount_pence: null, notes: "Synthetic unit price" };

async function fixture(page: Page, request: APIRequestContext): Promise<Fixture> {
  const token = await primePageAuth(page, request);
  const id = await createPatient(request, { first_name: "Synthetic", last_name: `Grouped planning ${Date.now()}` });
  await page.setViewportSize({ width: 1900, height: 1200 });
  return { id, endpoint: `${getBaseUrl()}/api/patients/${id}`, headers: { Authorization: `Bearer ${token}` } };
}
async function open(page: Page, value: Fixture) {
  await page.goto(`${getBaseUrl()}/patients/${value.id}/clinical?clinicalView=planned`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("treatment-planning-panel")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("planning-loading")).toHaveCount(0, { timeout: 30_000 });
}
async function read(request: APIRequestContext, value: Fixture, suffix: string) {
  const response = await request.get(`${value.endpoint}/${suffix}`, { headers: value.headers });
  expect(response.ok()).toBeTruthy(); return response.json();
}
async function seedMissing(request: APIRequestContext, value: Fixture, teeth: string[]) {
  const response = await request.post(`${value.endpoint}/clinical/tooth-conditions`, { headers: value.headers, data: { teeth, condition: "missing", expected_revisions: Object.fromEntries(teeth.map((tooth) => [tooth, 0])) } });
  expect(response.ok()).toBeTruthy();
}
async function createCatalogue(request: APIRequestContext, value: Fixture, kind: "bridge" | "denture", amount: number): Promise<Entry> {
  const defaults: Defaults = { drawing_kind: kind, material: kind === "bridge" ? "porcelain_bonded" : "denture_acrylic" };
  const response = await request.post(`${getBaseUrl()}/api/treatments`, { headers: value.headers, data: { name: `Synthetic ${kind} appliance ${value.id}`, code: `GROUP-${value.id}-${kind}`, level: "crown", planning_defaults: defaults, is_active: true } });
  expect(response.ok()).toBeTruthy(); const treatment = await response.json();
  const fees = await request.put(`${getBaseUrl()}/api/treatments/${treatment.id}/fees`, { headers: value.headers, data: [{ patient_category: "CLINIC_PRIVATE", fee_type: "FIXED", amount_pence: amount }] });
  expect(fees.ok()).toBeTruthy(); return treatment;
}
async function start(page: Page, request: APIRequestContext, value: Fixture): Promise<PlanningSnapshot> {
  await open(page, value); await page.getByTestId("planning-start").click();
  await expect(page.getByTestId("treatment-planning-chart")).toBeVisible();
  return (await read(request, value, "planning")).plan.snapshot;
}
async function groupDraft(page: Page, appliance: Appliance, treatment: Pick<Entry, "id" | "name">) {
  await page.getByTestId(`planning-add-${appliance.kind}`).click();
  await expect(page.getByTestId("planning-treatment-dialog")).toBeVisible();
  await page.getByTestId("planning-catalogue-search").fill(treatment.name);
  await page.getByTestId(`planning-catalogue-item-${treatment.id}`).click();
  await page.getByTestId("planning-group-arch").selectOption(appliance.arch);
  const selected = appliance.kind === "bridge" ? [appliance.members[0], appliance.members.at(-1)!] : appliance.members;
  for (const member of selected) await page.getByTestId(`planning-group-member-${member.tooth}`).click();
  if (appliance.kind === "bridge") for (const member of appliance.members) await page.getByTestId(`planning-group-role-${member.tooth}`).selectOption(member.role);
  for (const member of appliance.members) await expect(page.getByTestId("planning-group-summary")).toContainText(member.tooth);
}
async function more(page: Page) {
  const options = page.getByTestId("planning-more-options");
  if (await options.count() && !(await options.evaluate((element) => element instanceof HTMLDetailsElement ? element.open : element.getAttribute("aria-expanded") === "true"))) {
    const summary = options.locator(":scope > summary");
    if (await summary.count()) await summary.click(); else await options.click();
  }
}
async function save(page: Page, value: Fixture): Promise<{ item: Item; body: Record<string, unknown> }> {
  const saved = page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === `/api/patients/${value.id}/planning/items`);
  await page.getByTestId("planning-save").click(); const response = await saved; expect(response.ok()).toBeTruthy();
  const item = await response.json() as Item; await expect(page.getByTestId("planning-treatment-dialog")).toBeHidden();
  await expect(page.getByTestId(`planning-item-${item.id}`)).toBeVisible(); return { item, body: response.request().postDataJSON() };
}
async function complete(page: Page, value: Fixture, item: Item): Promise<Item> {
  await page.getByTestId(`planning-item-${item.id}`).click();
  const saved = page.waitForResponse((response) => response.request().method() === "PATCH" && new URL(response.url()).pathname === `/api/patients/${value.id}/planning/items/${item.id}`);
  page.once("dialog", (dialog) => dialog.accept()); await page.getByTestId("planning-action-complete").click();
  const response = await saved; expect(response.ok()).toBeTruthy();
  await expect(page.getByTestId(`planning-item-${item.id}`)).toHaveAttribute("data-status", "completed"); return response.json();
}
async function undo(page: Page, value: Fixture, item: Item) {
  await page.getByTestId(`planning-item-${item.id}`).click(); await page.getByTestId("planning-action-uncomplete").click();
  await page.getByTestId("planning-uncomplete-reason").fill("Synthetic grouped treatment correction");
  const saved = page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === `/api/patients/${value.id}/planning/items/${item.id}/uncomplete`);
  await page.getByTestId("planning-uncomplete-confirm").click(); expect((await saved).ok()).toBeTruthy();
  await expect(page.getByTestId("planning-uncomplete-dialog")).toBeHidden();
}
async function view(page: Page, mode: "current" | "planned") {
  await page.getByTestId(`clinical-chart-view-${mode}`).click();
  await expect(page.getByTestId(mode === "current" ? "clinical-chart" : "treatment-planning-chart")).toBeVisible({ timeout: 30_000 });
  if (mode === "current") await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/loading|saving/i);
  else await expect(page.getByTestId("planning-loading")).toHaveCount(0);
}
async function preserved(request: APIRequestContext, value: Fixture, original: Awaited<ReturnType<typeof read>>, snapshot: PlanningSnapshot) {
  const after = await read(request, value, "clinical/tooth-conditions");
  expect({ teeth: after.teeth, bridges: after.bridges, note_teeth: after.note_teeth }).toEqual({ teeth: original.teeth, bridges: original.bridges, note_teeth: original.note_teeth });
  expect((await read(request, value, "planning")).plan.snapshot).toEqual(snapshot);
}

test("real grouped bridge saves one three-unit quote and completes and uncompletes all roles with one charge", async ({ page, request }) => {
  const value = await fixture(page, request); await seedMissing(request, value, ["UL7"]);
  const treatment = await createCatalogue(request, value, "bridge", 12300);
  const native = await read(request, value, "clinical/tooth-conditions"), snapshot = await start(page, request, value);
  await groupDraft(page, bridge, treatment);
  await expect(page.getByTestId("planning-material")).toHaveValue("porcelain_bonded");
  await expect(page.getByTestId("planning-fee-basis")).toContainText(/unit/i);
  await expect(page.getByTestId("planning-fee-quantity")).toContainText("3");
  await expect(page.getByTestId("planning-fee-total")).toContainText("£369.00");
  const saved = await save(page, value);
  expect(saved.body).toMatchObject({ target: { level: "crown", tooth: null, surfaces: [] }, drawing_kind: "bridge", appliance: bridge, material: "porcelain_bonded", fee_mode: "catalogue" });
  expect(saved.item).toMatchObject({ appliance: bridge, fee_pence: 36900, pricing: { basis: "per_unit", quantity: 3, unit_fee_pence: 12300, total_fee_pence: 36900 } });
  expect(saved.item.catalogue_snapshot).toMatchObject({ fee: { amount_pence: 36900 }, unit_fee: { amount_pence: 12300 } });
  expect((await read(request, value, "planning")).plan.items).toHaveLength(1); expect(await read(request, value, "ledger")).toEqual([]);
  await page.getByTestId(`planning-item-${saved.item.id}`).click(); await page.getByTestId("planning-action-edit-fee").click();
  await expect(page.getByTestId("planning-fee-quote")).toContainText("£369.00");
  await page.getByTestId("planning-fee-mode").selectOption("override"); await page.getByTestId("planning-fee-amount").fill("360.01");
  await expect(page.getByTestId("planning-save")).toBeDisabled(); await page.getByTestId("planning-fee-reason").fill("Synthetic total appliance adjustment");
  await page.getByTestId("planning-save").click(); await expect(page.getByTestId("planning-treatment-dialog")).toBeHidden();
  await page.getByTestId("planning-action-edit-fee").click(); await page.getByTestId("planning-fee-mode").selectOption("catalogue");
  await page.getByTestId("planning-save").click(); await expect(page.getByTestId("planning-treatment-dialog")).toBeHidden();
  let item = (await read(request, value, "planning")).plan.items[0] as Item;
  expect(item).toMatchObject({ fee_pence: 36900, fee_reason: null, appliance: bridge, pricing: { quantity: 3, unit_fee_pence: 12300, total_fee_pence: 36900 } });
  await page.getByTestId("planning-action-material").click(); await page.getByTestId("planning-edit-material").selectOption("gold");
  await page.getByTestId("planning-material-save").click(); await expect(page.getByTestId("planning-material-dialog")).toBeHidden();
  item = await complete(page, value, item);
  for (const mode of ["current", "planned"] as const) {
    await view(page, mode);
    for (const member of bridge.members) {
      await expect(page.getByTestId(`clinical-crown-${member.tooth}`)).toHaveAttribute("data-bridge-role", member.role);
      await expect(page.getByTestId(`clinical-crown-${member.tooth}`)).toHaveAttribute("data-crown-kind", "gold");
    }
    await expect(page.getByTestId("clinical-crown-UL7")).toHaveAttribute("data-artificial-tooth", "pontic");
    await expect(page.getByTestId("clinical-root-UL7")).toHaveCount(0);
    await expect(page.getByTestId(`clinical-bridge-planning-${item.id}`)).toHaveAttribute("data-members", "UL6,UL7,UL8");
    await expect(page.getByTestId(`clinical-bridge-planning-${item.id}`)).toHaveAttribute("data-plan-status", "completed");
    const previews = path.join(process.cwd(), ".run", "planning-grouped-previews"); await mkdir(previews, { recursive: true });
    for (const theme of ["light", "dark"]) {
      await page.evaluate((value) => document.documentElement.dataset.theme = value, theme); await page.evaluate(() => scrollTo(0, 0));
      await page.getByTestId(mode === "current" ? "clinical-chart" : "treatment-planning-chart").screenshot({ path: path.join(previews, `${theme}-${mode}-completed-bridge.png`) });
    }
  }
  const charges = await read(request, value, "ledger"); expect(charges).toHaveLength(1); expect(charges[0].amount_pence).toBe(36900);
  for (const tooth of [null, ...bridge.members.map((member) => member.tooth)]) {
    const journal = await read(request, value, `clinical-journal?category=treatment${tooth ? `&tooth=${tooth}` : ""}`);
    const procedures = journal.items.filter((entry: { source_kind: string; source_id: string }) => entry.source_kind === "procedure" && entry.source_id === String(item.completed_procedure_id));
    expect(procedures).toHaveLength(1); expect(procedures[0].details.appliance).toEqual(bridge);
  }
  await preserved(request, value, native, snapshot);
  await view(page, "current"); await page.getByTestId("clinical-crown-UL7").click({ button: "right" });
  await page.getByTestId("clinical-crown-condition-porcelain").click();
  const crownSaved = page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === `/api/patients/${value.id}/clinical/crown-conditions`);
  await page.getByTestId("clinical-crown-apply").click(); expect((await crownSaved).ok()).toBeTruthy();
  await expect(page.getByTestId("clinical-crown-UL7")).toHaveAttribute("data-crown-kind", "porcelain");
  await expect(page.getByTestId("clinical-crown-UL7")).toHaveAttribute("data-artificial-tooth", "pontic");
  await expect(page.getByTestId("clinical-root-UL7")).toHaveCount(0);
  await expect(page.getByTestId(`clinical-bridge-planning-${item.id}`)).toHaveAttribute("data-members", "UL6,UL7,UL8");
  const afterCrownEdit = await read(request, value, "clinical/tooth-conditions"); expect(afterCrownEdit.teeth.UL7.crown_observation.kind).toBe("porcelain");
  await view(page, "planned"); await undo(page, value, item);
  for (const mode of ["current", "planned"] as const) {
    await view(page, mode); await expect(page.getByTestId("tooth-svg-UL7")).toHaveAttribute("data-baseline-status", "missing");
    await expect(page.getByTestId("tooth-crown-UL7")).toHaveCount(0);
    if (mode === "current") await expect(page.getByTestId(`clinical-bridge-planning-${item.id}`)).toHaveCount(0);
    else await expect(page.getByTestId(`clinical-bridge-planning-${item.id}`)).toHaveAttribute("data-plan-status", "planned");
  }
  const corrected = await read(request, value, "ledger"); expect(corrected).toHaveLength(2);
  expect(corrected.map((entry: { amount_pence: number }) => entry.amount_pence).sort((a: number, b: number) => a - b)).toEqual([-36900, 36900]);
  await preserved(request, value, afterCrownEdit, snapshot);
});

test("real noncontiguous denture uses one appliance price and restores all captured missing slots on undo", async ({ page, request }) => {
  const value = await fixture(page, request); await seedMissing(request, value, denture.members.map((member) => member.tooth));
  const treatment = await createCatalogue(request, value, "denture", 45600);
  const native = await read(request, value, "clinical/tooth-conditions"), snapshot = await start(page, request, value);
  await groupDraft(page, denture, treatment);
  await expect(page.getByTestId("planning-fee-basis")).toContainText(/appliance/i);
  await expect(page.getByTestId("planning-fee-quantity")).toContainText("1"); await expect(page.getByTestId("planning-fee-total")).toContainText("£456.00");
  const saved = await save(page, value);
  expect(saved.item).toMatchObject({ appliance: denture, fee_pence: 45600, pricing: { basis: "appliance", quantity: 1, total_fee_pence: 45600 } });
  expect((await read(request, value, "planning")).plan.items).toHaveLength(1); expect(await read(request, value, "ledger")).toEqual([]);
  const item = await complete(page, value, saved.item);
  for (const mode of ["current", "planned"] as const) {
    await view(page, mode);
    for (const { tooth } of denture.members) {
      await expect(page.getByTestId(`clinical-crown-${tooth}`)).toHaveAttribute("data-artificial-tooth", "denture");
      await expect(page.getByTestId(`clinical-denture-base-${tooth}`)).toHaveAttribute("data-denture-kind", "denture_acrylic");
      await expect(page.getByTestId(`clinical-root-${tooth}`)).toHaveCount(0);
    }
    await expect(page.getByTestId("clinical-crown-LL5")).not.toHaveAttribute("data-artificial-tooth", "denture");
  }
  const charges = await read(request, value, "ledger"); expect(charges).toHaveLength(1); expect(charges[0].amount_pence).toBe(45600);
  await undo(page, value, item); await view(page, "current");
  for (const { tooth } of denture.members) { await expect(page.getByTestId(`tooth-svg-${tooth}`)).toHaveAttribute("data-baseline-status", "missing"); await expect(page.getByTestId(`clinical-denture-base-${tooth}`)).toHaveCount(0); }
  await preserved(request, value, native, snapshot);
});

type Harness = Fixture & { state: PlanningResponse; entries: Entry[]; writes: Write[]; intercept: ((route: Route, write: Write) => Promise<boolean>) | null };
async function mock(page: Page, request: APIRequestContext): Promise<Harness> {
  const value = await fixture(page, request);
  const entry = (id: number, name: string, level: Entry["level"], defaults: Defaults | null): Entry => ({ id, name, level, code: `SYN-GROUP-${id}`, description: "Synthetic explicit treatment metadata", default_duration_minutes: 30, patient_category: "CLINIC_PRIVATE", fee: { ...unit }, quote_token: String(id).repeat(64).slice(0, 64), planning_defaults: defaults, planning_defaults_revision: defaults ? 1 : 0, suggested_planning_defaults: null, routine_key: null });
  const entries = [
    entry(1, "Synthetic bridge quote", "crown", { drawing_kind: "bridge", material: "porcelain_bonded" }),
    entry(2, "Synthetic denture quote", "crown", { drawing_kind: "denture", material: "denture_acrylic" }),
    entry(3, "Synthetic extraction default", "tooth", { drawing_kind: "extraction", material: null }),
    entry(4, "Synthetic unpriced filling", "surface", { drawing_kind: "filling", material: "gold" }),
    entry(5, "Synthetic crown in name without defaults", "crown", null),
    entry(6, "Synthetic owned routine suggestion", "tooth", null),
  ];
  entries[3].fee = { ...unit, type: "UNAVAILABLE", amount_pence: null, notes: null };
  entries[5].routine_key = "routine-v1:tooth:1"; entries[5].suggested_planning_defaults = { drawing_kind: "extraction", material: null };
  const state: PlanningResponse = { patient_id: Number(value.id), plan: { id: 50, created_at: "2030-01-07T09:00:00Z", created_by: null, snapshot: { version: 1, captured_at: "2030-01-07T09:00:00Z", native: { patient_id: Number(value.id), teeth: Object.fromEntries(["UL7", "LR5", "LL4", "LL6"].map((tooth) => [tooth, { revision: 1, condition: "missing" as const }])), note_teeth: [], bridges: [] }, legacy: null, coverage: { native: "captured", legacy: "unavailable", legacy_reason: "No imported chart linked" } }, items: [] }, earlier_items: [], earlier_items_total: 0 };
  const harness: Harness = { ...value, state, entries, writes: [], intercept: null };
  await page.route(`**/api/patients/${value.id}/planning**`, async (route) => {
    const req = route.request(), url = new URL(req.url());
    if (req.method() === "GET") {
      if (url.pathname.endsWith("/catalogue")) {
        const query = (url.searchParams.get("q") ?? "").toLowerCase(), level = url.searchParams.get("level"), applianceKind = url.searchParams.get("appliance_kind");
        const matching = entries.filter((item) => (!level || item.level === level) && (!applianceKind || (item.planning_defaults ?? item.suggested_planning_defaults)?.drawing_kind === applianceKind) && item.name.toLowerCase().includes(query));
        await route.fulfill({ json: { patient_id: Number(value.id), patient_category: "CLINIC_PRIVATE", currency: "GBP", practice_today: "2030-01-07", items: matching, total: matching.length } });
      } else await route.fulfill({ json: state });
      return;
    }
    const write: Write = { method: req.method(), path: url.pathname, body: req.postDataJSON(), requestId: req.headers()["request-id"] }; harness.writes.push(write);
    if (harness.intercept && await harness.intercept(route, write)) return;
    if (req.method() === "POST" && url.pathname.endsWith("/items")) {
      const body = write.body, treatment = entries.find((item) => item.id === body.treatment_id)!;
      const appliance = body.appliance as Appliance | undefined, target = body.target as Item["target"];
      const quantity = appliance?.kind === "bridge" ? appliance.members.length : 1;
      const total = body.fee_mode === "catalogue" ? (treatment.fee.amount_pence ?? 0) * quantity : Number(body.fee_pence);
      const item: Item = { id: 100 + state.plan!.items.length, patient_id: Number(value.id), plan_id: 50, treatment_id: treatment.id, revision: 1, target, tooth: target.tooth, surface: target.surfaces.join("") || null, drawing_kind: body.drawing_kind as PlanningDrawingKind, material: body.material as PlanningMaterial | null, appliance, pricing: appliance ? { basis: appliance.kind === "bridge" ? "per_unit" : "appliance", quantity, unit_fee_pence: treatment.fee.amount_pence, total_fee_pence: total } : undefined, catalogue_snapshot: { ...treatment, fee: { ...treatment.fee, amount_pence: treatment.fee.amount_pence == null ? null : treatment.fee.amount_pence * quantity } }, fee_mode: body.fee_mode as Item["fee_mode"], fee_reason: body.fee_reason as string | null, fee_pence: total, procedure_code: treatment.code!, description: treatment.name, status: "proposed", completed_procedure_id: null, created_at: "2030-01-07T10:00:00Z", updated_at: "2030-01-07T10:00:00Z" };
      state.plan!.items.push(item); await route.fulfill({ status: 201, json: item }); return;
    }
    if (req.method() === "PATCH") {
      const item = state.plan!.items.find((candidate) => candidate.id === Number(url.pathname.split("/").at(-1)))!;
      if (write.body.expected_revision !== item.revision) { await route.fulfill({ status: 409, json: { detail: "Synthetic revision conflict" } }); return; }
      if (write.body.fee_mode) { item.fee_mode = write.body.fee_mode as Item["fee_mode"]; item.fee_pence = Number(write.body.fee_pence); item.fee_reason = write.body.fee_reason as string | null; }
      item.revision += 1; await route.fulfill({ json: item }); return;
    }
    await route.fulfill({ status: 500, json: { detail: "Unexpected synthetic test mutation" } });
  });
  return harness;
}

test("stored routine defaults shorten add while incompatible surfaces clear and unpriced override and waiver remain explicit", async ({ page, request }) => {
  const harness = await mock(page, request); await open(page, harness);
  await page.getByTestId("clinical-surface-UR6-M").click();
  await page.getByTestId("planning-catalogue-item-3").click();
  await expect(page.getByTestId("planning-quick-summary")).toContainText("UR6"); await expect(page.getByTestId("planning-quick-summary")).toContainText("Extraction");
  await expect(page.getByTestId("planning-target-level")).toHaveCount(0); await expect(page.getByTestId("planning-drawing-kind")).toHaveCount(0);
  await expect(page.getByRole("group", { name: "Treatment surfaces", exact: true })).toHaveCount(0);
  const extraction = await save(page, harness);
  expect(extraction.body).toMatchObject({ target: { level: "tooth", tooth: "UR6", surfaces: [] }, drawing_kind: "extraction", fee_mode: "catalogue" });
  await page.getByTestId("clinical-surface-UR6-M").click(); await page.getByTestId("planning-catalogue-item-4").click();
  await expect(page.getByTestId("planning-material")).toHaveValue("gold"); await expect(page.getByTestId("planning-fee-mode")).toHaveCount(0);
  await expect(page.getByTestId("planning-fee-amount")).toHaveValue(""); await expect(page.getByTestId("planning-fee-quote")).not.toContainText("£0.00");
  await expect(page.getByTestId("planning-save")).toBeDisabled(); await page.getByTestId("planning-fee-amount").fill("42.00");
  await expect(page.getByTestId("planning-save")).toBeEnabled(); const agreed = await save(page, harness);
  expect(agreed.body).toMatchObject({ fee_mode: "agreed", fee_pence: 4200, fee_reason: "Patient-specific agreed fee; no practice price set" });
  await page.getByTestId("clinical-surface-UR6-M").click(); await page.getByTestId("planning-catalogue-item-4").click(); await more(page);
  await page.getByTestId("planning-fee-mode").selectOption("waived");
  await page.getByTestId("planning-fee-reason").fill(""); await expect(page.getByTestId("planning-save")).toBeDisabled();
  await page.getByTestId("planning-fee-reason").fill("Synthetic authorised waiver"); const waived = await save(page, harness);
  expect(waived.body).toMatchObject({ drawing_kind: "filling", material: "gold", fee_mode: "waived", fee_pence: 0, fee_reason: "Synthetic authorised waiver", target: { level: "surface", tooth: "UR6", surfaces: ["M"] } });
  await page.getByTestId("clinical-crown-UR6").click(); await page.getByTestId("planning-catalogue-item-5").click();
  await expect(page.getByTestId("planning-drawing-kind")).toHaveValue(""); await expect(page.getByTestId("planning-save")).toBeDisabled();
  await more(page); await page.getByTestId("planning-drawing-kind").selectOption("crown");
  await expect(page.getByTestId("planning-material")).toHaveValue(""); await expect(page.getByTestId("planning-save")).toBeEnabled();
  await page.getByTestId("planning-cancel").click();
  await page.getByTestId("clinical-crown-UR6").click(); await page.getByTestId("planning-catalogue-item-6").click();
  await expect(page.getByTestId("planning-quick-summary")).toContainText("Extraction"); await expect(page.getByTestId("planning-quick-summary")).toContainText("UR6");
  await expect(page.getByTestId("planning-save")).toBeEnabled(); await page.getByTestId("planning-cancel").click();
  await page.getByTestId("planning-add-bridge").click(); await expect(page.getByTestId("planning-catalogue-item-1")).toBeVisible();
  await expect(page.locator('[data-testid^="planning-catalogue-item-"]')).toHaveCount(1); await expect(page.getByTestId("planning-catalogue-item-3")).toHaveCount(0);
  await page.getByTestId("planning-catalogue-item-1").click(); await expect(page.getByTestId("planning-save")).toBeDisabled();
  await expect(page.getByTestId("planning-use-treatment-level")).toHaveCount(0);
  await page.getByTestId("planning-cancel").click(); expect(harness.writes).toHaveLength(3); expect(harness.entries[5].planning_defaults).toBeNull();
});

test("grouped pending and uncertain saves lock every member and safely retry the same whole-appliance request", async ({ page, request }) => {
  const harness = await mock(page, request); await open(page, harness); await groupDraft(page, bridge, harness.entries[0]);
  let release!: () => void; const gate = new Promise<void>((resolve) => { release = resolve; });
  harness.intercept = async (route) => { await gate; await route.abort("failed"); return true; };
  try {
    await page.getByTestId("planning-save").evaluate((element) => { (element as HTMLButtonElement).click(); (element as HTMLButtonElement).click(); });
    await expect(page.getByTestId("planning-save")).toBeDisabled(); await expect(page.getByTestId("planning-cancel")).toBeDisabled();
    await expect(page.getByTestId("planning-group-arch")).toBeDisabled(); await expect(page.getByTestId("planning-group-member-UL6")).toBeDisabled();
    await expect(page.getByTestId("planning-group-role-UL7")).toBeDisabled(); await expect(page.getByTestId("planning-material")).toBeDisabled();
    for (const key of ["Escape", "Control+1", "Meta+1"]) await page.keyboard.press(key);
    await expect(page.getByTestId("planning-treatment-dialog")).toBeVisible(); await expect.poll(() => harness.writes.length).toBe(1);
  } finally { release(); }
  await expect(page.getByTestId("planning-error")).toContainText(/could not be confirmed/i);
  await expect(page.getByTestId("planning-group-member-UL6")).toBeDisabled(); await expect(page.getByTestId("planning-material")).toBeDisabled();
  const attempted = structuredClone(harness.writes[0]); harness.intercept = null;
  await save(page, harness); expect(harness.writes).toHaveLength(2);
  expect(harness.writes[1]).toEqual(attempted); expect(attempted.requestId).toBeTruthy();
  expect(harness.state.plan!.items).toHaveLength(1); expect((harness.state.plan!.items[0] as Item).appliance).toEqual(bridge);
});

test("read-only users cannot add grouped treatment and older single-tooth bridge fees remain unchanged and editable for writers", async ({ page, request }) => {
  const harness = await mock(page, request);
  const old: Item = { id: 90, patient_id: Number(harness.id), plan_id: 50, treatment_id: 1, revision: 1, target: { level: "crown", tooth: "UR6", surfaces: [] }, tooth: "UR6", surface: null, drawing_kind: "bridge", material: "gold", catalogue_snapshot: { ...harness.entries[0], fee: { ...unit } }, fee_mode: "catalogue", fee_reason: null, fee_pence: 12300, procedure_code: "SYN-OLD", description: "Synthetic older single bridge unit", status: "proposed", completed_procedure_id: null, created_at: "2026-01-01T10:00:00Z", updated_at: "2026-01-01T10:00:00Z" };
  harness.state.plan!.items.push(old); const quote = structuredClone(old.catalogue_snapshot);
  await page.route("**/api/me/capabilities", (route) => route.fulfill({ json: ["patients.view", "clinical.view", "notes.view"] }));
  await open(page, harness);
  for (const action of ["treatment", "bridge", "denture"]) await expect(page.getByTestId(`planning-add-${action}`)).toBeDisabled();
  await page.getByTestId("planning-item-90").click(); await expect(page.getByTestId("planning-action-details")).toBeEnabled();
  for (const action of ["edit-fee", "material", "complete"]) await expect(page.getByTestId(`planning-action-${action}`)).toBeDisabled();
  expect(harness.writes).toEqual([]);
  await page.unroute("**/api/me/capabilities"); await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("planning-item-90")).toBeVisible({ timeout: 30_000 });
  await page.getByTestId("planning-item-90").click(); await page.getByTestId("planning-action-edit-fee").click();
  await expect(page.getByTestId("planning-fee-quote")).toContainText("£123.00"); await expect(page.getByTestId("planning-group-editor")).toHaveCount(0);
  await page.getByTestId("planning-fee-mode").selectOption("override"); await page.getByTestId("planning-fee-amount").fill("100");
  await page.getByTestId("planning-fee-reason").fill("Synthetic older item adjustment"); await page.getByTestId("planning-save").click();
  await expect(page.getByTestId("planning-treatment-dialog")).toBeHidden();
  expect(harness.writes).toEqual([{ method: "PATCH", path: `/api/patients/${harness.id}/planning/items/90`, requestId: expect.any(String), body: { expected_revision: 1, fee_mode: "override", fee_pence: 10000, fee_reason: "Synthetic older item adjustment" } }]);
  expect(old.target).toEqual({ level: "crown", tooth: "UR6", surfaces: [] }); expect(old.appliance).toBeUndefined(); expect(old.catalogue_snapshot).toEqual(quote);
});

test("grouped editors show explicit roles and totals in light dark and narrow layouts with keyboard access", async ({ page, request }) => {
  const harness = await mock(page, request); await open(page, harness);
  await page.getByTestId("planning-add-bridge").focus(); await page.keyboard.press("Enter");
  await page.getByTestId("planning-catalogue-item-1").click(); await page.getByTestId("planning-group-arch").selectOption("upper");
  for (const { tooth } of [bridge.members[0], bridge.members.at(-1)!]) { await page.getByTestId(`planning-group-member-${tooth}`).focus(); await page.keyboard.press("Space"); }
  for (const member of bridge.members) await expect(page.getByTestId(`planning-group-role-${member.tooth}`)).toHaveValue(member.role);
  for (const member of bridge.members) await page.getByTestId(`planning-group-role-${member.tooth}`).selectOption(member.role);
  await page.getByTestId("planning-material").selectOption(""); await expect(page.getByTestId("planning-save")).toBeDisabled();
  await expect(page.getByTestId("planning-validation")).toContainText(/material/i); await page.getByTestId("planning-material").selectOption("porcelain_bonded");
  await expect(page.getByTestId("planning-save")).toBeEnabled(); await expect(page.getByTestId("planning-fee-total")).toContainText("£369.00");
  const previews = path.join(process.cwd(), ".run", "planning-grouped-previews"); await mkdir(previews, { recursive: true });
  for (const theme of ["light", "dark"]) {
    await page.evaluate((value) => document.documentElement.dataset.theme = value, theme);
    await page.getByTestId("planning-treatment-dialog").screenshot({ path: path.join(previews, `${theme}-bridge-editor.png`) });
  }
  await page.setViewportSize({ width: 390, height: 844 }); await page.getByTestId("planning-cancel").scrollIntoViewIfNeeded();
  const bounds = (await page.getByTestId("planning-treatment-dialog").boundingBox())!;
  expect(bounds.x).toBeGreaterThanOrEqual(0); expect(bounds.x + bounds.width).toBeLessThanOrEqual(390);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  await page.screenshot({ path: path.join(previews, "mobile-bridge-editor.png") }); await page.getByTestId("planning-cancel").click();
  await page.setViewportSize({ width: 1900, height: 1200 }); await groupDraft(page, denture, harness.entries[1]);
  await page.getByTestId("planning-group-full").click(); await expect(page.getByTestId("planning-fee-quantity")).toContainText("1");
  await expect(page.getByTestId("planning-fee-total")).toContainText("£123.00");
  await page.getByTestId("planning-treatment-dialog").screenshot({ path: path.join(previews, "dark-full-denture-editor.png") });
  await page.getByTestId("planning-cancel").click(); expect(harness.writes).toEqual([]);
});

test("real practice planning defaults persist with revision conflicts and level validation without changing fees", async ({ page, request }) => {
  const value = await fixture(page, request), treatment = await createCatalogue(request, value, "bridge", 12300);
  const endpoint = `${getBaseUrl()}/api/treatments/${treatment.id}`;
  const fees = await request.get(`${endpoint}/fees`, { headers: value.headers }); expect(fees.ok()).toBeTruthy(); const originalFees = await fees.json();
  const current = async () => { const response = await request.get(endpoint, { headers: value.headers }); expect(response.ok()).toBeTruthy(); return response.json(); };
  const saveDefaults = async () => {
    const result = page.waitForResponse((response) => response.request().method() === "PATCH" && new URL(response.url()).pathname === `/api/treatments/${treatment.id}`);
    await page.getByTestId("treatment-save").click(); return result;
  };
  await page.goto(`${getBaseUrl()}/treatments`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId(`treatment-edit-${treatment.id}`)).toBeVisible({ timeout: 30_000 });
  await page.getByTestId(`treatment-edit-${treatment.id}`).click();
  await expect(page.getByTestId("treatment-planning-defaults")).toBeVisible();
  await expect(page.getByTestId("treatment-default-drawing")).toHaveValue("bridge");
  await page.getByTestId("treatment-default-drawing").selectOption("crown"); await expect(page.getByTestId("treatment-default-material")).toHaveValue("");
  await page.getByTestId("treatment-default-material").selectOption("gold");
  const first = await saveDefaults(); expect(first.ok()).toBeTruthy();
  expect(first.request().postDataJSON()).toMatchObject({ planning_defaults: { drawing_kind: "crown", material: "gold" }, expected_planning_defaults_revision: 1 });
  await expect(page.getByTestId("treatment-editor")).toBeHidden(); await page.reload({ waitUntil: "domcontentloaded" });
  await page.getByTestId(`treatment-edit-${treatment.id}`).click(); await expect(page.getByTestId("treatment-default-material")).toHaveValue("gold");
  const external = await request.patch(endpoint, { headers: value.headers, data: { planning_defaults: { drawing_kind: "crown", material: "porcelain" }, expected_planning_defaults_revision: 2 } });
  expect(external.ok()).toBeTruthy(); await page.getByTestId("treatment-default-material").selectOption("composite");
  const stale = await saveDefaults(); expect(stale.status()).toBe(409);
  await expect(page.getByTestId("treatment-editor").getByRole("alert")).toContainText(/changed|reopen/i);
  await expect(page.getByTestId("treatment-save")).toBeDisabled(); await expect(page.getByTestId("treatment-default-material")).toBeDisabled();
  expect(await current()).toMatchObject({ planning_defaults: { drawing_kind: "crown", material: "porcelain" }, planning_defaults_revision: 3 });
  await page.getByRole("button", { name: "Close treatment editor", exact: true }).click(); await page.getByTestId(`treatment-edit-${treatment.id}`).click();
  await expect(page.getByTestId("treatment-default-material")).toHaveValue("porcelain");
  await page.getByTestId("treatment-name").fill(`${treatment.name} renamed`);
  const rename = await saveDefaults(); expect(rename.ok()).toBeTruthy();
  expect(rename.request().postDataJSON()).not.toHaveProperty("planning_defaults"); expect(rename.request().postDataJSON()).not.toHaveProperty("expected_planning_defaults_revision");
  await expect(page.getByTestId("treatment-editor")).toBeHidden(); await page.getByTestId(`treatment-edit-${treatment.id}`).click();
  await page.getByTestId("treatment-level").selectOption("root");
  await expect(page.getByTestId("treatment-default-drawing")).toHaveValue(""); await expect(page.getByTestId("treatment-default-material")).toHaveCount(0);
  await expect(page.getByTestId("treatment-default-drawing").locator('option[value="crown"]')).toHaveCount(0);
  await page.getByTestId("treatment-default-drawing").selectOption("root_canal");
  const root = await saveDefaults(); expect(root.ok()).toBeTruthy();
  expect(root.request().postDataJSON()).toMatchObject({ level: "root", planning_defaults: { drawing_kind: "root_canal", material: null }, expected_planning_defaults_revision: 3 });
  const invalid = await request.patch(endpoint, { headers: value.headers, data: { planning_defaults: { drawing_kind: "crown", material: "gold" }, expected_planning_defaults_revision: 4 } });
  expect(invalid.status()).toBe(422); expect(await current()).toMatchObject({ level: "root", planning_defaults: { drawing_kind: "root_canal", material: null }, planning_defaults_revision: 4 });
  await expect(page.getByTestId("treatment-editor")).toBeHidden(); await page.getByTestId(`treatment-edit-${treatment.id}`).click();
  await page.getByTestId("treatment-level").selectOption("crown"); await page.getByTestId("treatment-default-drawing").selectOption("inlay_onlay");
  await page.getByTestId("treatment-default-material").selectOption("composite"); expect((await saveDefaults()).ok()).toBeTruthy();
  await expect(page.getByTestId("treatment-editor")).toBeHidden(); await page.getByTestId(`treatment-edit-${treatment.id}`).click();
  await page.getByTestId("treatment-level").selectOption("surface");
  await expect(page.getByTestId("treatment-default-drawing")).toHaveValue("inlay_onlay"); await expect(page.getByTestId("treatment-default-material")).toHaveValue("");
  expect((await saveDefaults()).ok()).toBeTruthy();
  expect(await current()).toMatchObject({ level: "surface", planning_defaults: { drawing_kind: "inlay_onlay", material: null }, planning_defaults_revision: 6 });
  const unchangedFees = await request.get(`${endpoint}/fees`, { headers: value.headers }); expect(await unchangedFees.json()).toEqual(originalFees);
  expect(await read(request, value, "ledger")).toEqual([]);
});
