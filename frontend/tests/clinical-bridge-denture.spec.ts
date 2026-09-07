import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

type Role = "abutment" | "pontic" | "wing";
type Member = { tooth: string; role: Role };
type Crown = { kind: string | null; issues: string[] };
type Row = {
  condition: string | null; revision: number; crown_observation: Crown | null;
  root_observations: Record<string, { condition: string | null; apicectomy: boolean }>;
  bridge_group_id: number | null; bridge_role: Role | null;
};
type Bridge = { id: number; arch: "upper" | "lower"; span_start: string; span_end: string; members: Member[] };
type Chart = { patient_id: number; teeth: Record<string, Row>; bridges: Bridge[]; note_teeth: string[] };
type Fixture = { patientId: string; headers: Record<string, string> };

const path = (id: string, suffix = "tooth-conditions") => `/api/patients/${id}/clinical/${suffix}`;
const canonical = ["UR8", "UR7", "UR6", "UR5", "UR4", "UR3", "UR2", "UR1", "UL1", "UL2", "UL3", "UL4", "UL5", "UL6", "UL7", "UL8", "LR8", "LR7", "LR6", "LR5", "LR4", "LR3", "LR2", "LR1", "LL1", "LL2", "LL3", "LL4", "LL5", "LL6", "LL7", "LL8"];
const ordered = (members: Member[]) => [...members].sort((a, b) => canonical.indexOf(a.tooth) - canonical.indexOf(b.tooth));

async function setup(page: Page, request: APIRequestContext, label: string): Promise<Fixture> {
  const token = await primePageAuth(page, request);
  const patientId = await createPatient(request, { first_name: "Synthetic", last_name: `${label} ${Date.now()}` });
  await page.setViewportSize({ width: 1440, height: 1050 });
  return { patientId, headers: { Authorization: `Bearer ${token}` } };
}

async function get(request: APIRequestContext, fixture: Fixture, suffix = "tooth-conditions"): Promise<Chart> {
  const response = await request.get(`${getBaseUrl()}${path(fixture.patientId, suffix)}`, { headers: fixture.headers });
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function post(request: APIRequestContext, fixture: Fixture, suffix: string, data: unknown): Promise<Chart> {
  const response = await request.post(`${getBaseUrl()}${path(fixture.patientId, suffix)}`, { headers: fixture.headers, data });
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function ready(page: Page) {
  await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/loading|saving/i);
}

async function open(page: Page, fixture: Fixture) {
  await page.goto(`${getBaseUrl()}/patients/${fixture.patientId}/clinical?clinicalView=current`, { waitUntil: "domcontentloaded" });
  await ready(page);
  await expect(page.getByTestId("clinical-diagnosis-palette")).toBeVisible();
}

function nextPost(page: Page, requestPath: string) {
  return page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === requestPath);
}

function watchWrites(page: Page, fixture: Fixture) {
  const writes: Array<{ path: string; body: unknown }> = [];
  page.on("request", (request) => {
    const pathname = new URL(request.url()).pathname;
    if (["POST", "PATCH", "PUT", "DELETE"].includes(request.method()) && pathname.startsWith(`/api/patients/${fixture.patientId}/`)) {
      writes.push({ path: pathname, body: request.postDataJSON() });
    }
  });
  return writes;
}

async function crownPalette(page: Page, tooth: string) {
  await page.getByTestId(`clinical-crown-${tooth}`).click();
  await expect(page.getByTestId("clinical-crown-diagnosis-palette")).toBeVisible();
}

async function editor(page: Page, tooth: string, role: Role = "abutment", context = false) {
  if (context) {
    await page.getByTestId(`clinical-crown-${tooth}`).click({ button: "right" });
    await page.getByTestId(`clinical-crown-bridge-${role}`).click();
  } else {
    await crownPalette(page, tooth);
    await page.getByTestId(`crown-diagnosis-bridge-${role}`).click();
  }
  await expect(page.getByTestId("clinical-bridge-editor")).toBeVisible();
  return page.getByTestId("clinical-bridge-editor");
}

async function span(page: Page, members: Member[], material?: string) {
  const list = ordered(members);
  await page.getByTestId("bridge-first").selectOption(list[0].tooth);
  await page.getByTestId("bridge-last").selectOption(list[list.length - 1].tooth);
  for (const member of list) await page.getByTestId(`bridge-role-${member.tooth}`).selectOption(member.role);
  if (material) await page.getByTestId("bridge-material").selectOption(material);
}

async function saveBridge(page: Page, fixture: Fixture) {
  const saved = nextPost(page, path(fixture.patientId, "bridges"));
  await page.getByTestId("bridge-save").click();
  const response = await saved;
  expect(response.ok()).toBeTruthy();
  await expect(page.getByTestId("clinical-bridge-editor")).toHaveCount(0);
  await ready(page);
  return { body: response.request().postDataJSON(), chart: await response.json() as Chart };
}

async function createBridge(request: APIRequestContext, fixture: Fixture, members: Member[], crown?: Crown) {
  const before = await get(request, fixture);
  const expected_revisions = Object.fromEntries(members.map(({ tooth }) => [tooth, before.teeth[tooth]?.revision ?? 0]));
  return post(request, fixture, "bridges", { members, expected_revisions, ...(crown ? { crown } : {}) });
}

async function refresh(page: Page) {
  await page.getByRole("button", { name: "Refresh conditions", exact: true }).click();
  await ready(page);
}

async function alignedBridge(page: Page, bridge: Bridge) {
  const target = page.getByTestId(`clinical-bridge-${bridge.id}`);
  const teeth = ordered(bridge.members).map(({ tooth }) => tooth);
  await expect(target).toHaveAttribute("data-members", teeth.join(","));
  await expect(target).toHaveAttribute("data-span-start", bridge.span_start);
  await expect(target).toHaveAttribute("data-span-end", bridge.span_end);
  await expect(target.locator("polyline")).toHaveCount(2);
  await expect(target).toHaveCSS("visibility", "visible");
  await expect(target.locator('polyline[stroke="#171717"]')).toHaveAttribute("stroke-width", "5");
  await expect.poll(async () => target.evaluate((group, members) => {
    const line = group.querySelector<SVGPolylineElement>('polyline[stroke="#171717"]');
    const grid = group.closest("svg")?.parentElement;
    const matrix = line?.getScreenCTM();
    if (!line || !grid || !matrix || line.points.numberOfItems !== members.length) return Infinity;
    return Math.max(...members.map((tooth, index) => {
      const crown = grid.querySelector<SVGPathElement>(`[data-testid="tooth-crown-${tooth}"]`);
      const crownMatrix = crown?.getScreenCTM();
      if (!crown || !crownMatrix) return Infinity;
      const bounds = crown.getBBox();
      const centre = new DOMPoint(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2).matrixTransform(crownMatrix);
      const point = line.points.getItem(index).matrixTransform(matrix);
      return Math.hypot(point.x - centre.x, point.y - centre.y);
    }));
  }, teeth)).toBeLessThan(1);
}

test("denture choices replace missing-tooth display without inventing roots or changing biological status", async ({ page, request }) => {
  const fixture = await setup(page, request, "Denture missing tooth batch");
  await post(request, fixture, "tooth-conditions", { teeth: ["UR6", "UR5"], condition: "missing", expected_revisions: { UR6: 0, UR5: 0 } });
  const financePath = `${getBaseUrl()}/api/patients/${fixture.patientId}/finance-summary`;
  const originalFinanceResponse = await request.get(financePath, { headers: fixture.headers });
  expect(originalFinanceResponse.ok()).toBeTruthy();
  const originalFinance = await originalFinanceResponse.json();
  await open(page, fixture);
  const writes = watchWrites(page, fixture);
  await expect(page.getByRole("button", { name: "UR6 crown area", exact: true })).toHaveCount(0);
  for (const [index, kind] of ["denture_cocr", "denture_acrylic"].entries()) {
    await crownPalette(page, index === 0 ? "UR7" : "UR6");
    await page.getByTestId(`crown-diagnosis-palette-${kind}`).click();
    await expect(page.locator('[data-testid^="crown-diagnosis-issue-"]')).toHaveCount(0);
    if (index === 0) {
      await page.getByTestId("clinical-crown-UR7").click();
      await expect(page.getByTestId("clinical-crown-placeholder-UR6")).toBeAttached();
      await expect(page.getByTestId("clinical-crown-UR6")).toHaveAttribute("data-crown-placeholder", "true");
      await page.getByTestId("clinical-crown-UR6").click();
    }
    await page.getByTestId("clinical-crown-UR5").click();
    await expect(page.getByTestId("crown-diagnosis-selection")).toContainText("UR6");
    const saved = nextPost(page, path(fixture.patientId, "crown-conditions"));
    await page.getByTestId("crown-diagnosis-apply").click();
    const response = await saved;
    expect(response.ok()).toBeTruthy();
    expect(response.request().postDataJSON()).toEqual({ teeth: ["UR6", "UR5"], kind, issues: [], expected_revisions: { UR6: index + 1, UR5: index + 1 } });
    const chart = await get(request, fixture);
    for (const tooth of ["UR6", "UR5"]) {
      expect(chart.teeth[tooth]).toMatchObject({ condition: "missing", revision: index + 2, root_observations: {}, crown_observation: { kind, issues: [] } });
      await expect(page.getByTestId(`clinical-crown-${tooth}`)).toHaveAttribute("data-artificial-tooth", "denture");
      await expect(page.getByTestId(`clinical-denture-base-${tooth}`)).toHaveAttribute("data-denture-kind", kind);
      await expect(page.getByTestId(`clinical-denture-base-${tooth}`)).toHaveAttribute("fill", kind === "denture_cocr" ? "#9eabb9" : "#d995ac");
      await expect(page.getByTestId(`clinical-root-${tooth}`)).toHaveCount(0);
      await expect(page.locator(`[data-testid^="tooth-root-${tooth}-"]`)).toHaveCount(0);
    }
    await page.reload({ waitUntil: "domcontentloaded" });
    await ready(page);
    await expect(page.getByTestId("clinical-crown-UR6")).toHaveAttribute("data-crown-kind", kind);
  }
  await crownPalette(page, "UR6");
  await page.getByTestId("crown-diagnosis-palette-reset").click();
  const reset = nextPost(page, path(fixture.patientId, "crown-conditions"));
  await page.getByTestId("crown-diagnosis-apply").click();
  expect((await reset).ok()).toBeTruthy();
  expect((await get(request, fixture)).teeth.UR6).toMatchObject({ condition: "missing", root_observations: {}, crown_observation: { kind: null, issues: [] } });
  await expect(page.getByTestId("clinical-denture-base-UR6")).toHaveCount(0);
  await expect(page.getByTestId("clinical-denture-base-UR5")).toBeAttached();
  expect(writes).toHaveLength(3);
  expect(writes.every((entry) => entry.path === path(fixture.patientId, "crown-conditions"))).toBeTruthy();
  const finalFinance = await request.get(financePath, { headers: fixture.headers });
  expect(await finalFinance.json()).toEqual(originalFinance);
});

test("bridge editor requires explicit unit roles and saves one connected group while retaining support roots and notes", async ({ page, request }) => {
  const fixture = await setup(page, request, "Bridge explicit support pontic roles");
  await post(request, fixture, "root-conditions", { teeth: ["UR7"], condition: "filled_sound", apicectomy: true, expected_revisions: { UR7: 0 } });
  await post(request, fixture, "tooth-conditions", { teeth: ["UR6"], condition: "missing", expected_revisions: { UR6: 0 } });
  const noteResponse = await request.post(`${getBaseUrl()}/api/patients/${fixture.patientId}/tooth-notes`, { headers: fixture.headers, data: { tooth: "UR7", surface: null, note: "Synthetic bridge support note must remain" } });
  expect(noteResponse.ok()).toBeTruthy();
  await open(page, fixture);
  const writes = watchWrites(page, fixture);
  await editor(page, "UR7");
  await page.getByTestId("bridge-first").selectOption("UR7");
  await page.getByTestId("bridge-last").selectOption("UR5");
  await expect(page.getByTestId("bridge-role-UR6")).toHaveValue("");
  await expect(page.getByTestId("bridge-role-UR5")).toHaveValue("");
  await expect(page.getByTestId("bridge-save")).toBeDisabled();
  const members: Member[] = [{ tooth: "UR7", role: "abutment" }, { tooth: "UR6", role: "pontic" }, { tooth: "UR5", role: "abutment" }];
  await span(page, members, "porcelain_bonded");
  expect(writes).toEqual([]);
  expect((await get(request, fixture)).bridges).toEqual([]);
  const saved = await saveBridge(page, fixture);
  expect(saved.body).toEqual({ members, expected_revisions: { UR7: 1, UR6: 1, UR5: 0 }, crown: { kind: "porcelain_bonded", issues: [] } });
  expect(saved.chart.bridges).toHaveLength(1);
  const bridge = saved.chart.bridges[0];
  expect(bridge).toMatchObject({ arch: "upper", span_start: "UR7", span_end: "UR5", members });
  for (const { tooth, role } of members) {
    expect(saved.chart.teeth[tooth]).toMatchObject({ bridge_group_id: bridge.id, bridge_role: role, crown_observation: { kind: "porcelain_bonded", issues: [] } });
    await expect(page.getByTestId(`clinical-crown-${tooth}`)).toHaveAttribute("data-bridge-role", role);
  }
  expect(saved.chart.teeth.UR6.condition).toBe("missing");
  await expect(page.getByTestId("clinical-crown-UR6")).toHaveAttribute("data-artificial-tooth", "pontic");
  await expect(page.getByTestId("clinical-root-UR6")).toHaveCount(0);
  await expect(page.locator('[data-testid^="clinical-root-finding-UR7-"]')).toHaveCount(3);
  await expect(page.getByTestId("tooth-note-flag-UR7")).toBeVisible();
  await expect(page.getByTestId(`clinical-bridge-${bridge.id}`)).toBeVisible();
  await page.reload({ waitUntil: "domcontentloaded" });
  await ready(page);
  expect((await get(request, fixture)).bridges).toEqual(saved.chart.bridges);
  await expect(page.getByTestId(`clinical-bridge-${bridge.id}`)).toBeVisible();
  expect(writes).toHaveLength(1);
});

test("separate bridge groups remain independent across adjacent teeth and a midline span resets only its confirmed group", async ({ page, request }) => {
  const fixture = await setup(page, request, "Independent bridge groups");
  await createBridge(request, fixture, [{ tooth: "UR7", role: "abutment" }, { tooth: "UR6", role: "pontic" }], { kind: "gold", issues: [] });
  await createBridge(request, fixture, [{ tooth: "UR5", role: "abutment" }, { tooth: "UR4", role: "pontic" }], { kind: "porcelain", issues: [] });
  const before = await createBridge(request, fixture, [{ tooth: "UR1", role: "wing" }, { tooth: "UL1", role: "pontic" }, { tooth: "UL2", role: "abutment" }], { kind: "porcelain_bonded", issues: [] });
  await open(page, fixture);
  const writes = watchWrites(page, fixture);
  for (const bridge of before.bridges) await alignedBridge(page, bridge);
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.getByTestId("clinical-chart").evaluate((chart) => {
    for (const node of Array.from(chart.querySelectorAll<HTMLElement>("*"))) {
      if (node.scrollWidth > node.clientWidth && ["auto", "scroll"].includes(getComputedStyle(node).overflowX)) node.scrollLeft = 100;
    }
    window.scrollTo(0, 360);
  });
  for (const bridge of before.bridges) await alignedBridge(page, bridge);
  await page.setViewportSize({ width: 1440, height: 1050 });
  const crossing = before.bridges.find((bridge) => bridge.span_start === "UR1")!;
  expect(crossing.members.map(({ tooth }) => tooth)).toEqual(["UR1", "UL1", "UL2"]);
  await expect(page.getByTestId("clinical-bridge-wing-UR1")).toBeAttached();
  await crownPalette(page, "UR1");
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.getByTestId(`bridge-reset-${crossing.id}`).click();
  expect(writes).toEqual([]);
  expect((await get(request, fixture)).bridges).toEqual(before.bridges);
  const reset = nextPost(page, path(fixture.patientId, `bridges/${crossing.id}/reset`));
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByTestId(`bridge-reset-${crossing.id}`).click();
  const response = await reset;
  expect(response.ok()).toBeTruthy();
  expect(response.request().postDataJSON()).toEqual({ expected_revisions: { UR1: 1, UL1: 1, UL2: 1 } });
  const after = await get(request, fixture);
  expect(after.bridges).toEqual(before.bridges.filter((bridge) => bridge.id !== crossing.id));
  for (const { tooth } of crossing.members) expect(after.teeth[tooth]).toMatchObject({ condition: null, revision: 2, crown_observation: { kind: null, issues: [] }, bridge_group_id: null, bridge_role: null });
  for (const tooth of ["UR7", "UR6", "UR5", "UR4"]) expect(after.teeth[tooth]).toEqual(before.teeth[tooth]);
  await expect(page.getByTestId(`clinical-bridge-${crossing.id}`)).toHaveCount(0);
  expect(writes).toHaveLength(1);
});

test("invalid roles and overlapping spans cannot create partial bridge groups or erase a member", async ({ page, request }) => {
  const fixture = await setup(page, request, "Bridge validation safety");
  await open(page, fixture);
  const writes = watchWrites(page, fixture);
  await editor(page, "UR7");
  await expect(page.getByTestId("bridge-last").locator("option")).toHaveCount(16);
  expect(await page.getByTestId("bridge-last").locator("option").evaluateAll((options) => options.every((option) => option.textContent?.startsWith("U")))).toBeTruthy();
  await page.getByTestId("bridge-first").selectOption("LR7");
  await expect(page.getByTestId("bridge-last")).toHaveValue("LR7");
  await expect(page.getByTestId("bridge-role-LR7")).toHaveValue("");
  expect(await page.getByTestId("bridge-last").locator("option").evaluateAll((options) => options.every((option) => option.textContent?.startsWith("L")))).toBeTruthy();
  await span(page, [{ tooth: "UR7", role: "abutment" }, { tooth: "UR6", role: "abutment" }]);
  await expect(page.getByTestId("bridge-save")).toBeDisabled();
  await page.getByTestId("bridge-role-UR7").selectOption("pontic");
  await page.getByTestId("bridge-role-UR6").selectOption("pontic");
  await expect(page.getByTestId("bridge-save")).toBeDisabled();
  await page.getByTestId("bridge-cancel").click();
  expect(writes).toEqual([]);
  expect((await get(request, fixture)).teeth).toEqual({});
  const before = await createBridge(request, fixture, [{ tooth: "UR7", role: "abutment" }, { tooth: "UR6", role: "pontic" }]);
  await page.reload({ waitUntil: "domcontentloaded" });
  await ready(page);
  await editor(page, "UR5");
  await span(page, [{ tooth: "UR6", role: "pontic" }, { tooth: "UR5", role: "abutment" }]);
  await expect(page.getByTestId("bridge-save")).toBeDisabled();
  await page.getByTestId("bridge-cancel").click();
  await crownPalette(page, "UR7");
  await page.getByTestId("crown-diagnosis-palette-reset").click();
  const failed = nextPost(page, path(fixture.patientId, "crown-conditions"));
  await page.getByTestId("crown-diagnosis-apply").click();
  expect((await failed).status()).toBe(422);
  await expect(page.getByTestId("clinical-baseline-error")).toBeVisible();
  expect((await get(request, fixture)).bridges).toEqual(before.bridges);
  for (const tooth of ["UR7", "UR6"]) expect((await get(request, fixture)).teeth[tooth]).toEqual(before.teeth[tooth]);
  await alignedBridge(page, before.bridges[0]);
});

test("stale bridge creation and group reset reject atomically against the shared tooth revisions", async ({ page, request }) => {
  const fixture = await setup(page, request, "Bridge shared revision conflicts");
  await open(page, fixture);
  await editor(page, "UR7", "abutment", true);
  await expect(page.getByTestId("bridge-first")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("clinical-bridge-editor")).toHaveCount(0);
  await expect(page.getByTestId("clinical-crown-UR7")).toBeFocused();
  await page.keyboard.press("Shift+F10");
  await page.getByTestId("clinical-crown-bridge-abutment").click();
  await expect(page.getByTestId("bridge-first")).toBeFocused();
  const members: Member[] = [{ tooth: "UR7", role: "abutment" }, { tooth: "UR6", role: "pontic" }, { tooth: "UR5", role: "abutment" }];
  await span(page, members, "metal");
  await post(request, fixture, "root-conditions", { teeth: ["UR7"], condition: "filled_sound", expected_revisions: { UR7: 0 } });
  const failed = nextPost(page, path(fixture.patientId, "bridges"));
  await page.getByTestId("bridge-save").click();
  expect((await failed).status()).toBe(409);
  const afterConflict = await get(request, fixture);
  expect(afterConflict.bridges).toEqual([]);
  expect(Object.keys(afterConflict.teeth)).toEqual(["UR7"]);
  expect(afterConflict.teeth.UR7.bridge_group_id).toBeNull();
  await page.getByTestId("bridge-cancel").click();
  await refresh(page);
  const recorded = await createBridge(request, fixture, members, { kind: "gold", issues: [] });
  await page.reload({ waitUntil: "domcontentloaded" });
  await ready(page);
  const bridge = recorded.bridges[0];
  await crownPalette(page, "UR7");
  const changed = await post(request, fixture, "crown-conditions", { teeth: ["UR7"], kind: "porcelain_bonded", issues: ["defective"], expected_revisions: { UR7: recorded.teeth.UR7.revision } });
  const reset = nextPost(page, path(fixture.patientId, `bridges/${bridge.id}/reset`));
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByTestId(`bridge-reset-${bridge.id}`).click();
  expect((await reset).status()).toBe(409);
  const final = await get(request, fixture);
  expect(final.bridges).toEqual(changed.bridges);
  for (const { tooth } of members) expect(final.teeth[tooth]).toEqual(changed.teeth[tooth]);
  await refresh(page);
  await expect(page.getByTestId("clinical-crown-UR7")).toHaveAttribute("data-crown-kind", "porcelain_bonded");
  await expect(page.getByTestId(`clinical-bridge-${bridge.id}`)).toBeVisible();
});

test("pending failed and read-only bridge interactions never imply successful saves", async ({ page, request }) => {
  const fixture = await setup(page, request, "Bridge pending and read only");
  await open(page, fixture);
  await editor(page, "UR7");
  await span(page, [{ tooth: "UR7", role: "abutment" }, { tooth: "UR6", role: "pontic" }]);
  await expect(page.getByTestId("bridge-material")).toHaveValue("keep");
  let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route(`**${path(fixture.patientId, "bridges")}`, async (route) => {
    await gate;
    await route.fulfill({ status: 500, contentType: "text/plain", body: "synthetic private bridge infrastructure diagnostic" });
  });
  const response = nextPost(page, path(fixture.patientId, "bridges"));
  try {
    await page.getByTestId("bridge-save").click();
    await expect(page.getByTestId("bridge-save")).toBeDisabled();
    await expect(page.getByTestId("bridge-cancel")).toBeDisabled();
    await expect(page.getByTestId("clinical-bridge-editor")).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByTestId("clinical-bridge-editor")).toBeFocused();
    await page.keyboard.press("Shift+Tab");
    await expect(page.getByTestId("clinical-bridge-editor")).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("clinical-bridge-editor")).toBeVisible();
    expect((await get(request, fixture)).bridges).toEqual([]);
  } finally { release(); }
  const failedResponse = await response;
  expect(failedResponse.status()).toBe(500);
  expect(failedResponse.request().postDataJSON()).toEqual({
    members: [{ tooth: "UR7", role: "abutment" }, { tooth: "UR6", role: "pontic" }],
    expected_revisions: { UR7: 0, UR6: 0 },
  });
  await expect(page.getByText("synthetic private bridge infrastructure diagnostic")).toHaveCount(0);
  await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/saved/i);
  await page.getByTestId("bridge-cancel").click();
  await page.unroute(`**${path(fixture.patientId, "bridges")}`);
  await page.route("**/api/me/capabilities", (route) => route.fulfill({ json: ["patients.view", "clinical.view"] }));
  await open(page, fixture);
  const writes = watchWrites(page, fixture);
  await crownPalette(page, "UR7");
  for (const role of ["abutment", "pontic", "wing"]) await expect(page.getByTestId(`crown-diagnosis-bridge-${role}`)).toBeDisabled();
  for (const kind of ["denture_cocr", "denture_acrylic"]) await expect(page.getByTestId(`crown-diagnosis-palette-${kind}`)).toBeDisabled();
  for (const mode of ["planned", "history"]) {
    await page.getByTestId(`clinical-chart-view-${mode}`).click();
    await expect(page.getByTestId("clinical-bridge-editor")).toHaveCount(0);
    await expect(page.getByTestId("clinical-crown-diagnosis-palette")).toHaveCount(0);
    await page.getByTestId("clinical-chart-view-current").click();
    await ready(page);
  }
  expect(writes).toEqual([]);
  expect((await get(request, fixture)).teeth).toEqual({});
});

test("bridges dentures and enlarged crown choices remain readable in light dark and mobile previews", async ({ page, request }, testInfo) => {
  const fixture = await setup(page, request, "Bridge and denture visual preview");
  await createBridge(request, fixture, [{ tooth: "UR7", role: "abutment" }, { tooth: "UR6", role: "pontic" }, { tooth: "UR5", role: "abutment" }], { kind: "porcelain_bonded", issues: [] });
  await createBridge(request, fixture, [{ tooth: "UR1", role: "wing" }, { tooth: "UL1", role: "pontic" }], { kind: "metal", issues: [] });
  await post(request, fixture, "tooth-conditions", { teeth: ["LR6", "LR5", "LL5", "LL6"], condition: "missing", expected_revisions: { LR6: 0, LR5: 0, LL5: 0, LL6: 0 } });
  await post(request, fixture, "crown-conditions", { teeth: ["LR6", "LR5"], kind: "denture_cocr", issues: [], expected_revisions: { LR6: 1, LR5: 1 } });
  await post(request, fixture, "crown-conditions", { teeth: ["LL5", "LL6"], kind: "denture_acrylic", issues: [], expected_revisions: { LL5: 1, LL6: 1 } });
  await page.setViewportSize({ width: 1900, height: 2300 });
  await open(page, fixture);
  const writes = watchWrites(page, fixture);
  await crownPalette(page, "UR7");
  const symbol = page.getByTestId("crown-diagnosis-palette-porcelain_bonded").locator("svg");
  expect(await symbol.evaluate((node) => parseFloat(getComputedStyle(node).width))).toBeCloseTo(44.85, 1);
  const capture = async (name: string) => {
    await page.evaluate(() => { window.scrollTo(0, 0); return new Promise<void>((resolve) => requestAnimationFrame(() => resolve())); });
    const image = testInfo.outputPath(`${name}.png`);
    await page.screenshot({ path: image, fullPage: true });
    await testInfo.attach(name, { path: image, contentType: "image/png" });
  };
  await capture("bridge-denture-light");
  const chartBox = await page.getByTestId("clinical-chart").boundingBox();
  const paletteBox = await page.getByTestId("clinical-crown-diagnosis-palette").boundingBox();
  expect(chartBox).not.toBeNull();
  expect(paletteBox).not.toBeNull();
  const x = Math.max(0, Math.min(chartBox!.x, paletteBox!.x) - 8);
  const y = Math.max(0, chartBox!.y - 8);
  const right = Math.max(chartBox!.x + chartBox!.width, paletteBox!.x + paletteBox!.width) + 8;
  const bottom = paletteBox!.y + paletteBox!.height + 8;
  expect(right).toBeLessThanOrEqual(1900);
  expect(bottom).toBeLessThanOrEqual(2300);
  const closeup = testInfo.outputPath("bridge-denture-chart-palette-closeup.png");
  await page.screenshot({ path: closeup, clip: { x, y, width: right - x, height: bottom - y } });
  await testInfo.attach("bridge-denture-chart-palette-closeup", { path: closeup, contentType: "image/png" });
  await page.getByRole("button", { name: "Toggle theme", exact: true }).click();
  await capture("bridge-denture-dark");
  await editor(page, "UL5", "wing", true);
  await span(page, [{ tooth: "UL5", role: "wing" }, { tooth: "UL6", role: "pontic" }]);
  const dialogImage = testInfo.outputPath("bridge-editor-dark.png");
  await page.screenshot({ path: dialogImage });
  await testInfo.attach("bridge-editor-dark", { path: dialogImage, contentType: "image/png" });
  await page.setViewportSize({ width: 390, height: 844 });
  const dialogBox = await page.getByTestId("clinical-bridge-editor").boundingBox();
  expect(dialogBox).not.toBeNull();
  expect(dialogBox!.x).toBeGreaterThanOrEqual(0);
  expect(dialogBox!.x + dialogBox!.width).toBeLessThanOrEqual(390);
  expect(dialogBox!.y + dialogBox!.height).toBeLessThanOrEqual(844);
  await page.getByTestId("bridge-save").scrollIntoViewIfNeeded();
  await expect(page.getByTestId("bridge-save")).toBeVisible();
  const mobileDialog = testInfo.outputPath("bridge-editor-mobile.png");
  await page.screenshot({ path: mobileDialog });
  await testInfo.attach("bridge-editor-mobile", { path: mobileDialog, contentType: "image/png" });
  await page.getByTestId("bridge-cancel").click();
  await capture("bridge-denture-mobile");
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(391);
  expect(writes).toEqual([]);
});
