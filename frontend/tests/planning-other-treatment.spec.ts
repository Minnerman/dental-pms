import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

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

test("catalogue defaults to the selected level plus unassigned and Other can switch back without changing the target", async ({ page, request }) => {
  const { id } = await fixture(page, request), queries: URLSearchParams[] = [], writes: string[] = [];
  const entries = [
    { id: 1, name: "Sample whole-tooth item", level: "tooth" },
    { id: 2, name: "Sample root item", level: "root" },
    { id: 3, name: "Sample unassigned item", level: null },
    { id: 4, name: "Sample general item", level: "general" },
  ].map((entry) => ({ ...entry, display_order: entry.id, code: `SYN${entry.id}`, description: "Synthetic classified catalogue item", default_duration_minutes: 30, patient_category: "CLINIC_PRIVATE", fee: { type: "FIXED", amount_pence: 12500, min_amount_pence: null, max_amount_pence: null, notes: null }, quote_token: String(entry.id).repeat(64) }));
  await page.route(`**/api/patients/${id}/planning**`, async (route) => {
    const req = route.request(), url = new URL(req.url());
    if (req.method() !== "GET") { writes.push(url.pathname); await route.fulfill({ status: 500, json: { detail: "This inspection test must not write" } }); return; }
    if (url.pathname.endsWith("/catalogue")) {
      queries.push(url.searchParams); const level = url.searchParams.get("level"), includeUnassigned = url.searchParams.get("include_unassigned") !== "false";
      const items = entries.filter((entry) => !level || entry.level === level || (entry.level === null && includeUnassigned));
      await route.fulfill({ json: { patient_id: Number(id), patient_category: "CLINIC_PRIVATE", currency: "GBP", items, total: items.length } }); return;
    }
    await route.fulfill({ json: { patient_id: Number(id), plan: { id: 10, created_at: "2030-01-07T09:00:00Z", created_by: null, snapshot: { version: 1, captured_at: "2030-01-07T09:00:00Z", native: { patient_id: Number(id), teeth: {}, note_teeth: [], bridges: [] }, legacy: null, coverage: { native: "captured", legacy: "unavailable", legacy_reason: "No imported chart linked" } }, items: [] }, earlier_items: [], earlier_items_total: 0 } });
  });
  await open(page, id); await page.getByTestId("clinical-root-UR6").click(); await expect(page.getByTestId("planning-treatment-dialog")).toBeVisible();
  await expect(page.getByTestId("planning-catalogue-item-2")).toBeVisible(); await expect(page.getByTestId("planning-catalogue-item-3")).toBeVisible(); await expect(page.getByTestId("planning-catalogue-item-1")).toHaveCount(0); await expect(page.getByTestId("planning-catalogue-item-4")).toHaveCount(0);
  expect(queries.at(-1)!.get("level")).toBe("root"); expect(queries.at(-1)!.get("include_unassigned")).toBe("true");
  await page.getByTestId("planning-catalogue-scope").selectOption("all"); await expect(page.getByTestId("planning-catalogue-item-1")).toBeVisible(); await expect(page.getByTestId("planning-catalogue-item-4")).toBeVisible(); expect(queries.at(-1)!.has("level")).toBeFalsy();
  await page.getByTestId("planning-catalogue-item-1").click(); await expect(page.getByTestId("planning-validation")).toContainText(/level|match|classified/i); await expect(page.getByTestId("planning-save")).toBeDisabled();
  await page.getByTestId("planning-other-treatment").click(); await page.getByTestId("planning-other-description").fill("Unsaved custom root description"); await page.getByTestId("planning-use-catalogue").click();
  await expect(page.getByTestId("planning-target-level")).toHaveValue("root"); await expect(page.getByTestId("planning-target-tooth")).toHaveValue("UR6"); await expect(page.getByTestId("planning-other-description")).toHaveCount(0);
  await page.getByTestId("planning-cancel").click(); await expect(page.getByTestId("planning-treatment-dialog")).toBeHidden(); expect(writes).toEqual([]);
});
