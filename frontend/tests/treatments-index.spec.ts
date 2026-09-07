import { expect, test, type APIRequestContext, type Page, type Route } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

type Level = "tooth" | "root" | "crown" | "surface" | "general" | null;
type EffectiveFee = {
  version_id: number | null; effective_from: string | null; revision: number; source: "legacy" | "version";
  fee_type: "FIXED" | "RANGE" | "N_A" | null; amount_pence: number | null;
  min_amount_pence: number | null; max_amount_pence: number | null; notes: string | null;
};
type IndexItem = {
  id: number; name: string; code: string; description: string; level: Level; display_order: number;
  is_active: boolean; default_duration_minutes: number | null; is_denplan_included_default: boolean;
  current_fee: EffectiveFee | null; scheduled_fees: EffectiveFee[]; fee_revision: number;
  created_at: string; updated_at: string; created_by_user_id: number; updated_by_user_id: number;
};
type Write = { path: string; method: string; body: Record<string, unknown>; requestId: string | undefined };
const today = "2030-01-07";
const tomorrow = "2030-01-08";
function fee(amount = 12500, patch: Partial<EffectiveFee> = {}): EffectiveFee {
  return { version_id: null, effective_from: null, revision: 0, source: "legacy", fee_type: "FIXED", amount_pence: amount, min_amount_pence: null, max_amount_pence: null, notes: "Synthetic practice fee", ...patch };
}
function item(id: number, name: string, level: Level, patch: Partial<IndexItem> = {}): IndexItem {
  return { id, name, code: `SYN${id}`, description: "Synthetic catalogue example", level, display_order: id,
    is_active: true, default_duration_minutes: 30, is_denplan_included_default: false,
    current_fee: fee(), scheduled_fees: [], fee_revision: 0,
    created_at: "2029-12-01T10:00:00Z", updated_at: "2029-12-01T10:00:00Z", created_by_user_id: 1, updated_by_user_id: 1, ...patch };
}
async function auth(page: Page, request: APIRequestContext) {
  const token = await primePageAuth(page, request); await page.setViewportSize({ width: 1440, height: 1000 });
  return { Authorization: `Bearer ${token}` };
}
async function mock(page: Page, request: APIRequestContext) {
  await auth(page, request);
  const entries = [item(6, "Sample unassigned", null), item(3, "Sample crown", "crown"), item(2, "Sample root", "root"), item(5, "Sample general", "general"), item(4, "Sample surface", "surface"), item(1, "Sample tooth", "tooth"), item(7, "First tooth by practice order", "tooth", { display_order: 0 })];
  const harness = { entries, reads: [] as string[], writes: [] as Write[], failIndex: false, indexGate: null as Promise<void> | null, failHistory: null as number | null,
    routineResult: { created: 0, existing: 20, total: 20 }, routineItems: [] as IndexItem[],
    intercept: null as ((route: Route, write: Write) => Promise<boolean>) | null };
  await page.route("**/api/treatments**", async (route) => {
    const req = route.request(), url = new URL(req.url());
    if (req.method() === "GET") {
      harness.reads.push(url.pathname + url.search);
      if (url.pathname.endsWith("/index")) {
        if (harness.indexGate) await harness.indexGate;
        if (harness.failIndex) { await route.fulfill({ status: 503, json: { detail: "Synthetic index unavailable" } }); return; }
        await route.fulfill({ json: { practice_today: today, timezone: "Europe/London", currency: "GBP", patient_category: url.searchParams.get("patient_category") ?? "CLINIC_PRIVATE", items: entries } }); return;
      }
      if (url.pathname.endsWith("/fee-history")) {
        const id = Number(url.pathname.split("/").at(-2)), selected = entries.find((entry) => entry.id === id)!;
        if (harness.failHistory === id) { await route.fulfill({ status: 503, json: { detail: "Synthetic history unavailable" } }); return; }
        await route.fulfill({ json: { treatment_id: id, patient_category: url.searchParams.get("patient_category") ?? "CLINIC_PRIVATE", fee_revision: selected.fee_revision, baseline_fee: selected.current_fee?.source === "legacy" ? selected.current_fee : null, items: [...selected.scheduled_fees, ...(selected.current_fee?.source === "version" ? [selected.current_fee] : [])], next_before_revision: null } }); return;
      }
      await route.fulfill({ json: entries }); return;
    }
    const write: Write = { path: url.pathname, method: req.method(), body: req.postDataJSON(), requestId: req.headers()["request-id"] }; harness.writes.push(write);
    if (harness.intercept && await harness.intercept(route, write)) return;
    if (url.pathname.endsWith("/routine-defaults")) {
      for (const entry of harness.routineItems) if (!entries.some((existing) => existing.id === entry.id)) entries.push(entry);
      await route.fulfill({ json: harness.routineResult }); return;
    }
    const id = Number(url.pathname.endsWith("/fee-changes") ? url.pathname.split("/").at(-2) : url.pathname.split("/").at(-1));
    const selected = entries.find((entry) => entry.id === id);
    if (!selected) { await route.fulfill({ status: 404, json: { detail: "Synthetic treatment not found" } }); return; }
    if (url.pathname.endsWith("/fee-changes")) {
      if (selected.fee_revision !== write.body.expected_revision) { await route.fulfill({ status: 409, json: { detail: "Synthetic fee revision conflict" } }); return; }
      selected.fee_revision += 1;
      const next = fee(0, { version_id: 100 + selected.fee_revision, source: "version", revision: selected.fee_revision, effective_from: String(write.body.effective_from), fee_type: write.body.fee_type as EffectiveFee["fee_type"], amount_pence: write.body.amount_pence as number | null ?? null, min_amount_pence: write.body.min_amount_pence as number | null ?? null, max_amount_pence: write.body.max_amount_pence as number | null ?? null, notes: write.body.notes as string | null ?? null });
      if (next.effective_from! <= today) selected.current_fee = next; else selected.scheduled_fees.push(next);
    } else Object.assign(selected, write.body);
    await route.fulfill({ json: selected });
  });
  return harness;
}
async function open(page: Page, throughPracticeMenu = false) {
  if (throughPracticeMenu) {
    await page.goto(`${getBaseUrl()}/patients`, { waitUntil: "domcontentloaded" });
    await page.getByTestId("app-sidebar").getByRole("button", { name: "More", exact: true }).click();
    await page.getByRole("navigation", { name: "Administration" }).getByRole("link", { name: "Treatments", exact: true }).click();
    await expect(page).toHaveURL(/\/treatments$/);
  } else await page.goto(`${getBaseUrl()}/treatments`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("treatments-page")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("treatments-loading")).toHaveCount(0, { timeout: 30_000 });
}
async function editFees(page: Page, id: number) { await page.getByTestId(`treatment-fees-${id}`).click(); await expect(page.getByTestId("fee-editor")).toBeVisible(); }
async function closeFees(page: Page) { await page.getByTestId("fee-editor").getByRole("button", { name: /^close|^cancel/i }).first().click(); await expect(page.getByTestId("fee-editor")).toBeHidden(); }

test("treatments are grouped in clinical order and editing does not refetch or overwrite the draft", async ({ page, request }) => {
  const harness = await mock(page, request); await open(page, true);
  await expect(page.locator('[data-testid^="treatments-group-"]')).toHaveCount(6);
  expect(await page.locator('[data-testid^="treatments-group-"]').evaluateAll((groups) => groups.map((group) => group.getAttribute("data-testid")))).toEqual(["tooth", "root", "crown", "surface", "general", "unassigned"].map((level) => `treatments-group-${level}`));
  expect(await page.getByTestId("treatments-group-tooth").locator('[data-testid^="treatment-row-"]').evaluateAll((rows) => rows.map((row) => row.getAttribute("data-testid")))).toEqual(["treatment-row-7", "treatment-row-1"]);
  const reads = harness.reads.length;
  await page.getByTestId("treatment-edit-1").click(); await expect(page.getByTestId("treatment-editor")).toBeVisible();
  await page.getByTestId("treatment-name").fill("Unsaved synthetic name"); await page.getByTestId("treatment-level").selectOption("root");
  await page.getByTestId("treatment-name").press("Tab"); await expect(page.getByTestId("treatment-name")).toHaveValue("Unsaved synthetic name");
  expect(harness.reads).toHaveLength(reads); expect(harness.writes).toHaveLength(0);
  await page.getByTestId("treatment-save").click(); await expect(page.getByTestId("treatment-editor")).toBeHidden();
  expect(harness.writes).toHaveLength(1); expect(harness.writes[0]).toMatchObject({ path: "/api/treatments/1", method: "PATCH", body: { name: "Unsaved synthetic name", level: "root" } });
  await expect(page.getByTestId("treatments-group-root").getByTestId("treatment-row-1")).toContainText("Unsaved synthetic name");
});

test("real current and future practice fees survive reload and same-date corrections retain history", async ({ page, request }) => {
  const headers = await auth(page, request), endpoint = `${getBaseUrl()}/api/treatments`;
  const created = await request.post(endpoint, { headers, data: { name: `Synthetic practice fee ${Date.now()}`, code: `PF${Date.now()}`, level: "root", display_order: 75, is_active: true } });
  expect(created.ok()).toBeTruthy(); const treatment = await created.json();
  const index = await request.get(`${endpoint}/index?patient_category=CLINIC_PRIVATE`, { headers }); expect(index.ok()).toBeTruthy(); const indexData = await index.json();
  const date = indexData.practice_today as string, future = new Date(`${date}T12:00:00Z`); future.setUTCDate(future.getUTCDate() + 1); const futureDate = future.toISOString().slice(0, 10);
  await open(page); await editFees(page, treatment.id); await page.getByTestId("fee-type").selectOption("FIXED"); await page.getByTestId("fee-amount").fill("48.75"); await page.getByTestId("fee-effective-date").fill(date);
  await page.getByTestId("fee-save").click(); await expect(page.getByTestId("fee-editor")).toBeHidden(); await expect(page.getByTestId(`fee-current-${treatment.id}`)).toContainText("£48.75");
  await editFees(page, treatment.id); await page.getByTestId("fee-amount").fill("52.50"); await page.getByTestId("fee-effective-date").fill(futureDate); await page.getByTestId("fee-notes").fill("Synthetic future practice fee"); await page.getByTestId("fee-save").click(); await expect(page.getByTestId("fee-editor")).toBeHidden();
  await expect(page.getByTestId(`fee-current-${treatment.id}`)).toContainText("£48.75"); await expect(page.getByTestId(`fee-scheduled-${treatment.id}`)).toContainText("£52.50");
  await editFees(page, treatment.id); await page.getByTestId("fee-effective-date").fill(futureDate); await page.getByTestId("fee-amount").fill("54.25"); await page.getByTestId("fee-notes").fill("Synthetic correction to future fee"); await page.getByTestId("fee-save").click(); await expect(page.getByTestId("fee-editor")).toBeHidden();
  await page.reload({ waitUntil: "domcontentloaded" }); await expect(page.getByTestId(`fee-current-${treatment.id}`)).toContainText("£48.75", { timeout: 30_000 }); await expect(page.getByTestId(`fee-scheduled-${treatment.id}`)).toContainText("£54.25");
  const history = await request.get(`${endpoint}/${treatment.id}/fee-history?patient_category=CLINIC_PRIVATE`, { headers }); expect(history.ok()).toBeTruthy(); const versions = await history.json();
  expect(versions.items).toHaveLength(3); expect(versions.items.map((version: EffectiveFee) => version.amount_pence).sort((a: number, b: number) => a - b)).toEqual([4875, 5250, 5425]);
  await editFees(page, treatment.id); await page.getByTestId("fee-history").locator(":scope > summary").click(); await expect(page.getByTestId("fee-history")).toContainText("£52.50"); await expect(page.getByTestId("fee-history")).toContainText("£54.25");
});

test("fee validation distinguishes blank and invalid amounts from an explicitly recorded zero", async ({ page, request }) => {
  const harness = await mock(page, request); harness.entries.find((entry) => entry.id === 1)!.current_fee = fee(0); await open(page); await editFees(page, 1);
  await expect(page.getByTestId("fee-amount")).toHaveValue("0.00"); await expect(page.getByTestId("fee-save")).toBeEnabled();
  for (const value of ["", " ", "-1", "1.001", "1000000.01"]) { await page.getByTestId("fee-amount").fill(value); await page.getByTestId("fee-save").click(); await expect(page.getByTestId("fee-editor")).toBeVisible(); expect(harness.writes).toHaveLength(0); }
  await page.getByTestId("fee-type").selectOption("RANGE"); await page.getByTestId("fee-min").fill("10"); await page.getByTestId("fee-max").fill(""); await page.getByTestId("fee-save").click(); expect(harness.writes).toHaveLength(0);
  await page.getByTestId("fee-max").fill("5"); await page.getByTestId("fee-save").click(); await expect(page.getByTestId("fee-editor").getByRole("alert")).toContainText(/minimum.*greater|range/i); expect(harness.writes).toHaveLength(0);
  await page.getByTestId("fee-type").selectOption("FIXED"); await page.getByTestId("fee-amount").fill("0"); await page.getByTestId("fee-effective-date").fill("2030-01-06"); await page.getByTestId("fee-save").click(); expect(harness.writes).toHaveLength(0);
  await page.getByTestId("fee-effective-date").fill(today); await page.getByTestId("fee-save").click(); await expect(page.getByTestId("fee-editor")).toBeHidden();
  expect(harness.writes).toHaveLength(1); expect(harness.writes[0].body).toMatchObject({ fee_type: "FIXED", amount_pence: 0, expected_revision: 0, effective_from: today, patient_category: "CLINIC_PRIVATE" });
  await editFees(page, 1); await expect(page.getByTestId("fee-amount")).toHaveValue("0.00");
});

test("fee saves lock one treatment and reject stale data without hiding the draft or applying to another row", async ({ page, request }) => {
  const harness = await mock(page, request); await open(page); await editFees(page, 1); await page.getByTestId("fee-amount").fill("135");
  let release!: () => void; const gate = new Promise<void>((resolve) => { release = resolve; });
  harness.intercept = async (route) => { await gate; await route.fulfill({ status: 409, json: { detail: "Synthetic fee revision changed" } }); return true; };
  try {
    await page.getByTestId("fee-save").evaluate((button) => { (button as HTMLButtonElement).click(); (button as HTMLButtonElement).click(); });
    await expect(page.getByTestId("fee-save")).toBeDisabled(); await expect(page.getByTestId("fee-amount")).toBeDisabled(); await expect(page.getByTestId("fee-effective-date")).toBeDisabled();
    await page.keyboard.press("Escape"); await expect(page.getByTestId("fee-editor")).toBeVisible(); expect(harness.writes).toHaveLength(1);
  } finally { release(); }
  await expect(page.getByTestId("fee-editor").getByRole("alert")).toContainText(/changed|refresh|conflict/i); await expect(page.getByTestId("fee-amount")).toHaveValue("135");
  expect(harness.writes[0].path).toBe("/api/treatments/1/fee-changes"); expect(harness.writes[0].requestId).toBeTruthy(); expect(harness.entries.find((entry) => entry.id === 2)!.current_fee!.amount_pence).toBe(12500);
  await expect(page.getByTestId("fee-save")).toBeDisabled();
  await closeFees(page); harness.failHistory = 2; await editFees(page, 2); await page.getByTestId("fee-history").locator(":scope > summary").click(); await expect(page.getByTestId("fee-history").getByRole("alert")).toContainText(/could not|unavailable|failed/i);
  await expect(page.getByTestId("fee-amount")).toHaveValue("125.00"); await expect(page.getByTestId("fee-editor").getByRole("heading")).toContainText("Sample root");
  await expect(page.getByTestId("fee-save")).toBeEnabled(); expect(harness.writes).toHaveLength(1);
  let uncertainResponse = true; harness.failHistory = null;
  harness.intercept = async (route) => { if (!uncertainResponse) return false; uncertainResponse = false; await route.fulfill({ status: 503, json: { detail: "Synthetic unknown fee save" } }); return true; };
  await page.getByTestId("fee-amount").fill("150"); await page.getByTestId("fee-save").click();
  await expect(page.getByTestId("fee-editor").getByRole("alert").first()).toContainText(/could not be confirmed/i); await expect(page.getByTestId("fee-amount")).toBeDisabled();
  await expect(page.getByTestId("fee-save")).toHaveText("Retry unchanged fee"); await page.getByTestId("fee-save").click(); await expect(page.getByTestId("fee-editor")).toBeHidden();
  expect(harness.writes).toHaveLength(3); expect(harness.writes[1].requestId).toBeTruthy(); expect(harness.writes[2]).toEqual(harness.writes[1]);
  await expect(page.getByTestId("fee-current-2")).toContainText("£150.00"); await expect(page.getByTestId("fee-current-1")).toContainText("£125.00");
});

test("a denied or failed treatment index never exposes an editable successful empty catalogue", async ({ page, request }) => {
  const harness = await mock(page, request); harness.failIndex = true; await open(page);
  await expect(page.getByTestId("treatments-error")).toBeVisible(); await expect(page.locator('[data-testid^="treatment-row-"]')).toHaveCount(0);
  await expect(page.getByTestId("treatments-add-routine")).toBeDisabled(); expect(harness.writes).toHaveLength(0);
  await page.route("**/api/treatments/index?**", (route) => route.fulfill({ status: 403, json: { detail: "Synthetic administrator permission required" } }));
  await page.reload({ waitUntil: "domcontentloaded" }); await expect(page.getByTestId("treatments-error")).toContainText(/administrator|permission|access/i, { timeout: 30_000 });
  await expect(page.getByTestId("treatment-editor")).toBeHidden(); await expect(page.getByTestId("fee-editor")).toBeHidden(); expect(harness.writes).toHaveLength(0);
});

test("grouped current and scheduled practice fees fit light dark and mobile with readable history", async ({ page, request }) => {
  const harness = await mock(page, request); harness.entries.find((entry) => entry.id === 2)!.scheduled_fees = [fee(13500, { version_id: 1, effective_from: tomorrow, revision: 1, source: "version" })];
  harness.entries.find((entry) => entry.id === 4)!.current_fee = fee(0, { fee_type: "RANGE", amount_pence: null, min_amount_pence: 8000, max_amount_pence: 14000 }); harness.entries.find((entry) => entry.id === 5)!.current_fee = null;
  await page.emulateMedia({ reducedMotion: "reduce" }); await open(page); const previews = path.join(process.cwd(), ".run", "treatments-index-previews"); await mkdir(previews, { recursive: true });
  await page.setViewportSize({ width: 1280, height: 1000 });
  for (const theme of ["light", "dark"]) { await page.evaluate((value) => { document.documentElement.dataset.theme = value; scrollTo(0, 0); }, theme); await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1); await page.screenshot({ path: path.join(previews, `${theme}-treatments.png`), fullPage: true }); }
  await page.setViewportSize({ width: 390, height: 844 }); await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  await page.screenshot({ path: path.join(previews, "mobile-treatments.png"), fullPage: true }); await editFees(page, 2); await page.getByTestId("fee-history").locator(":scope > summary").click(); await expect(page.getByTestId("fee-history")).toContainText("£135.00");
  await page.getByTestId("fee-save").scrollIntoViewIfNeeded(); const save = (await page.getByTestId("fee-save").boundingBox())!; expect(save.x).toBeGreaterThanOrEqual(0); expect(save.x + save.width).toBeLessThanOrEqual(390);
  await page.screenshot({ path: path.join(previews, "mobile-fee-history.png") }); expect(harness.writes).toHaveLength(0);
});

test("routine treatment confirmation is in-page and cancellation never submits or opens a browser confirmation", async ({ page, request }) => {
  const harness = await mock(page, request); await page.emulateMedia({ reducedMotion: "reduce" }); await open(page);
  const browserDialogs: string[] = []; page.on("dialog", async (dialog) => { browserDialogs.push(dialog.type()); await dialog.dismiss(); });
  const opener = page.getByTestId("treatments-add-routine"), confirmation = page.getByTestId("routine-treatments-dialog");
  await opener.click(); await expect(confirmation).toBeVisible(); await expect(confirmation.getByRole("heading")).toHaveText("Add missing routine treatments");
  await expect(page.getByTestId("routine-treatments-confirm")).toHaveText("Add missing treatments"); expect(harness.writes).toEqual([]); expect(browserDialogs).toEqual([]);
  const previews = path.join(process.cwd(), ".run", "treatments-routine-previews"); await mkdir(previews, { recursive: true });
  for (const theme of ["light", "dark"]) { await page.evaluate((value) => document.documentElement.dataset.theme = value, theme); await page.screenshot({ path: path.join(previews, `${theme}-routine-confirmation.png`) }); }
  await page.setViewportSize({ width: 390, height: 844 }); const bounds = (await confirmation.boundingBox())!;
  expect(bounds.x).toBeGreaterThanOrEqual(0); expect(bounds.x + bounds.width).toBeLessThanOrEqual(390); expect(bounds.y).toBeGreaterThanOrEqual(0); expect(bounds.y + bounds.height).toBeLessThanOrEqual(844);
  await page.screenshot({ path: path.join(previews, "mobile-routine-confirmation.png") }); await page.setViewportSize({ width: 1440, height: 1000 });
  let releaseRead!: () => void; harness.indexGate = new Promise<void>((resolve) => { releaseRead = resolve; });
  try {
    await confirmation.getByRole("button", { name: "Cancel", exact: true }).click(); await expect(confirmation).toBeHidden(); await expect(opener).toBeDisabled();
  } finally { harness.indexGate = null; releaseRead(); }
  await expect(opener).toBeFocused();
  await opener.click(); await expect(confirmation).toBeVisible(); await page.keyboard.press("Escape"); await expect(confirmation).toBeHidden(); await expect(opener).toBeFocused();
  expect(harness.writes).toEqual([]); expect(browserDialogs).toEqual([]);
});

test("routine confirmation reports newly added versus already present treatments without inventing fees", async ({ page, request }) => {
  const harness = await mock(page, request); harness.routineResult = { created: 2, existing: 18, total: 20 };
  harness.routineItems = [item(101, "Synthetic missing tooth routine", "tooth", { current_fee: null }), item(102, "Synthetic missing root routine", "root", { current_fee: null })];
  const originalFees = harness.entries.map((entry) => ({ id: entry.id, fee: structuredClone(entry.current_fee) })); await open(page);
  const browserDialogs: string[] = []; page.on("dialog", async (dialog) => { browserDialogs.push(dialog.type()); await dialog.dismiss(); });
  await page.getByTestId("treatments-add-routine").click(); expect(harness.writes).toEqual([]);
  await page.getByTestId("routine-treatments-confirm").click();
  const confirmation = page.getByTestId("routine-treatments-dialog"), result = page.getByTestId("routine-treatments-result");
  await expect(result).toHaveAttribute("role", "status"); await expect(result).toContainText("Added 2 missing routine treatments"); await expect(result).toContainText("Existing treatments and fees were kept");
  await expect(confirmation).toBeVisible(); expect(harness.writes).toHaveLength(1); expect(harness.writes[0]).toMatchObject({ path: "/api/treatments/routine-defaults", method: "POST", body: {} });
  await confirmation.getByRole("button", { name: "Close treatment editor", exact: true }).click(); await expect(confirmation).toBeHidden();
  await expect(page.getByTestId("fee-current-101")).toHaveText("Not set"); await expect(page.getByTestId("fee-current-102")).toHaveText("Not set");
  expect(harness.entries.filter((entry) => originalFees.some((original) => original.id === entry.id)).map((entry) => ({ id: entry.id, fee: entry.current_fee }))).toEqual(originalFees);
  harness.routineResult = { created: 0, existing: 20, total: 20 };
  await page.getByTestId("treatments-add-routine").click(); await page.getByTestId("routine-treatments-confirm").click();
  await expect(result).toContainText("All 20 routine treatments are already in your index"); await expect(result).toContainText("Nothing needed adding"); await expect(result).toContainText("Add treatment");
  expect(harness.writes).toHaveLength(2); expect(harness.entries.filter((entry) => entry.id >= 101)).toHaveLength(2); expect(browserDialogs).toEqual([]);
});

test("routine confirmation blocks duplicate pending saves and retries an unconfirmed response with the same request", async ({ page, request }) => {
  const harness = await mock(page, request); await open(page);
  const browserDialogs: string[] = []; page.on("dialog", async (dialog) => { browserDialogs.push(dialog.type()); await dialog.dismiss(); });
  const confirmation = page.getByTestId("routine-treatments-dialog"), confirm = page.getByTestId("routine-treatments-confirm");
  let release!: () => void; const gate = new Promise<void>((resolve) => { release = resolve; }); let first = true;
  harness.intercept = async (route) => { if (!first) return false; first = false; await gate; await route.fulfill({ status: 503, json: { detail: "Synthetic routine result not confirmed" } }); return true; };
  await page.getByTestId("treatments-add-routine").click();
  try {
    await confirm.evaluate((button) => { (button as HTMLButtonElement).click(); (button as HTMLButtonElement).click(); });
    await expect(confirm).toBeDisabled(); await expect(confirmation).toContainText("Checking routine treatments"); await expect(confirmation.getByRole("button", { name: "Close treatment editor", exact: true })).toBeDisabled();
    await page.keyboard.press("Escape"); await expect(confirmation).toBeVisible(); expect(harness.writes).toHaveLength(1); expect(browserDialogs).toEqual([]);
  } finally { release(); }
  await expect(confirmation.getByRole("alert")).toBeVisible(); await expect(confirm).toHaveText("Retry safely"); await expect(confirm).toBeEnabled();
  await confirm.click(); await expect(page.getByTestId("routine-treatments-result")).toContainText("already in your index");
  expect(harness.writes).toHaveLength(2); expect(harness.writes[0].requestId).toBeTruthy(); expect(harness.writes[1]).toEqual(harness.writes[0]);
  await confirmation.getByRole("button", { name: "Close treatment editor", exact: true }).click(); await expect(confirmation).toBeHidden();
  harness.intercept = async (route) => { await route.fulfill({ json: { created: 2, existing: 20, total: 20 } }); return true; };
  await page.getByTestId("treatments-add-routine").click(); await confirm.click(); await expect(confirmation.getByRole("alert")).toBeVisible();
  await expect(page.getByTestId("routine-treatments-result")).toHaveCount(0);
  await confirmation.getByRole("button", { name: "Close treatment editor", exact: true }).click(); await expect(confirmation).toBeHidden();
  expect(harness.writes).toHaveLength(3); expect(browserDialogs).toEqual([]);
});
