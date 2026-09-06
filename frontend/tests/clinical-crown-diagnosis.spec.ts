import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

const crownKinds = ["missing", "metal", "gold", "porcelain", "porcelain_bonded", "composite"] as const;
const crownIssues = ["decayed", "defective", "fractured", "poor_fitting"] as const;
type CrownKind = typeof crownKinds[number] | "fractured";
type CrownIssue = typeof crownIssues[number];
type CrownObservation = { kind: CrownKind | null; issues: CrownIssue[] };
type CrownMutation = CrownObservation & { teeth: string[]; expected_revisions: Record<string, number> };
type Snapshot = {
  patient_id: number;
  teeth: Record<string, {
    condition: string | null;
    revision: number;
    crown_observation: CrownObservation | null;
    root_observations: Record<string, { condition: string | null; apicectomy: boolean }>;
  }>;
  note_teeth: string[];
};

function toothPath(patientId: string) { return `/api/patients/${patientId}/clinical/tooth-conditions`; }
function rootPath(patientId: string) { return `/api/patients/${patientId}/clinical/root-conditions`; }
function crownPath(patientId: string) { return `/api/patients/${patientId}/clinical/crown-conditions`; }

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

async function recordCrown(request: APIRequestContext, patientId: string, headers: Record<string, string>, data: CrownMutation) {
  const response = await request.post(`${getBaseUrl()}${crownPath(patientId)}`, { headers, data });
  expect(response.ok()).toBeTruthy();
  return response.json() as Promise<Snapshot>;
}

async function ready(page: Page) {
  await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/loading|saving/i);
}

async function openChart(page: Page, patientId: string) {
  await page.goto(`${getBaseUrl()}/patients/${patientId}/clinical?clinicalView=current`, { waitUntil: "domcontentloaded" });
  await ready(page);
  await expect(page.getByTestId("clinical-diagnosis-palette")).toBeVisible();
}

async function activateCrown(page: Page, tooth: string) {
  await page.getByTestId(`clinical-crown-${tooth}`).click();
  await expect(page.getByTestId("clinical-crown-diagnosis-palette")).toBeVisible();
  await expect(page.getByTestId("clinical-diagnosis-palette")).toHaveCount(0);
  await expect(page.getByTestId("clinical-root-diagnosis-palette")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Close tooth tools", exact: true })).toHaveCount(0);
}

async function openCrownMenu(page: Page, tooth: string) {
  await page.getByTestId(`clinical-crown-${tooth}`).click({ button: "right" });
  const menu = page.getByTestId("clinical-crown-action-menu");
  await expect(menu).toBeVisible();
  await expect(menu).toHaveAccessibleName(`Crown area actions for ${tooth}`);
  return menu;
}

function nextSave(page: Page, path: string) {
  return page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === path);
}

async function applyCrown(page: Page, patientId: string, context = false) {
  const saved = nextSave(page, crownPath(patientId));
  await page.getByTestId(context ? "clinical-crown-apply" : "crown-diagnosis-apply").click();
  const response = await saved;
  expect(response.ok()).toBeTruthy();
  await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/saving/i);
  return response.request().postDataJSON() as CrownMutation;
}

async function crownDrawing(page: Page, tooth: string, observation: CrownObservation | null) {
  const target = page.getByTestId(`clinical-crown-${tooth}`);
  await expect(target).toHaveAttribute("data-crown-kind", observation ? observation.kind ?? "unspecified" : "untouched");
  await expect(target).toHaveAttribute("data-crown-recorded", String(observation !== null));
  const issues = observation?.issues ?? [];
  await expect(target).toHaveAttribute("data-crown-issues", [...issues].sort().join(","));
  for (const issue of crownIssues) await expect(page.getByTestId(`clinical-crown-issue-${tooth}-${issue}`)).toHaveCount(issues.includes(issue) ? 1 : 0);
  await expect(page.getByTestId(`clinical-crown-hit-${tooth}`)).toBeAttached();
  await expect(page.getByTestId(`clinical-crown-stump-${tooth}`)).toHaveCount(observation?.kind === "missing" ? 1 : 0);
  await expect(page.getByTestId(`tooth-crown-${tooth}`)).toHaveCount(observation?.kind === "fractured" || observation?.kind === "missing" ? 0 : 1);
  if (observation?.kind === "porcelain_bonded") {
    await expect(page.getByTestId(`tooth-crown-${tooth}`)).toHaveAttribute("fill", "#70483b");
  }
}

function observeWrites(page: Page, patientId: string) {
  const crowns: CrownMutation[] = [];
  const other: string[] = [];
  page.on("request", (outgoing) => {
    if (!["POST", "PUT", "PATCH", "DELETE"].includes(outgoing.method())) return;
    const path = new URL(outgoing.url()).pathname;
    if (path === crownPath(patientId)) crowns.push(outgoing.postDataJSON() as CrownMutation);
    else if (/\/api\/(?:patients|invoices|payments|treatment)/.test(path)) other.push(path);
  });
  return { crowns, other };
}

async function selectCrowns(page: Page, kind: CrownKind | "reset", teeth: string[], issues: CrownIssue[] = []) {
  await activateCrown(page, teeth[0]);
  await page.getByTestId(`crown-diagnosis-palette-${kind}`).click();
  await expect(page.getByTestId(`crown-diagnosis-palette-${kind}`)).toHaveAttribute("aria-pressed", "true");
  for (const issue of issues) await page.getByTestId(`crown-diagnosis-issue-${issue}`).check();
  for (const tooth of teeth.slice(1)) await page.getByTestId(`clinical-crown-${tooth}`).click();
  for (const tooth of teeth) await expect(page.getByTestId(`clinical-crown-${tooth}`)).toHaveAttribute("data-crown-selected", "true");
}

function expectMutation(actual: CrownMutation, expected: CrownMutation) {
  expect({ ...actual, issues: [...actual.issues].sort() }).toEqual({ ...expected, issues: [...expected.issues].sort() });
}

test("crown palette and staged context menu are separate from root and tooth choices", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "Crown palette switching");
  await openChart(page, patientId);
  const writes = observeWrites(page, patientId);
  await expect(page.getByRole("button", { name: "UR6 crown area", exact: true })).toHaveCount(1);
  await activateCrown(page, "UR6");
  await expect(page.getByTestId("clinical-crown-action-menu")).toHaveCount(0);
  await expect(page.getByTestId("crown-diagnosis-selection")).toContainText("UR6");
  await expect(page.getByTestId("crown-diagnosis-apply")).toBeDisabled();
  const palette = page.getByTestId("clinical-crown-diagnosis-palette");
  for (const kind of [...crownKinds, "reset", "denture_cocr", "denture_acrylic"]) {
    await expect(palette.getByTestId(`crown-diagnosis-palette-${kind}`)).toHaveCount(1);
  }
  await expect(palette.getByTestId("crown-diagnosis-palette-fractured")).toHaveCount(0);
  await page.getByTestId("crown-diagnosis-palette-metal").click();
  for (const issue of crownIssues) await expect(page.getByTestId(`crown-diagnosis-issue-${issue}`)).not.toBeChecked();
  await page.getByTestId("crown-diagnosis-issue-decayed").check();
  await page.getByTestId("crown-diagnosis-palette-gold").click();
  await expect(page.getByTestId("crown-diagnosis-issue-decayed")).not.toBeChecked();
  await expect(page.getByTestId("clinical-crown-diagnosis-palette")).toContainText(/not specified|unspecified/i);
  await page.getByTestId("clinical-root-UR6").click();
  await expect(page.getByTestId("clinical-root-diagnosis-palette")).toBeVisible();
  await expect(page.getByTestId("clinical-crown-diagnosis-palette")).toHaveCount(0);
  await expect(page.locator('[data-crown-selected="true"]')).toHaveCount(0);
  await activateCrown(page, "LR6");
  await expect(page.locator('[data-root-selected="true"]')).toHaveCount(0);
  await page.getByTestId("tooth-label-UR6").click();
  await expect(page.getByTestId("clinical-diagnosis-palette")).toBeVisible();
  await expect(page.getByTestId("clinical-crown-diagnosis-palette")).toHaveCount(0);
  await page.keyboard.press("Escape");

  const menu = await openCrownMenu(page, "UR6");
  await expect(menu.getByTestId("clinical-crown-condition-fractured")).toHaveCount(0);
  await expect(page.getByTestId("clinical-root-action-menu")).toHaveCount(0);
  await expect(page.getByTestId("clinical-tooth-action-menu")).toHaveCount(0);
  await expect(page.getByTestId("clinical-chart-menu-add-procedure")).toHaveCount(0);
  await expect(page.getByTestId("clinical-chart-menu-add-plan")).toHaveCount(0);
  await menu.getByTestId("clinical-crown-condition-gold").click();
  await menu.getByTestId("clinical-crown-issue-defective").check();
  await expect(menu.getByTestId("clinical-crown-apply")).toBeEnabled();
  expect((await snapshot(request, patientId, headers)).teeth).toEqual({});
  expect(writes.crowns).toEqual([]);
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("clinical-crown-UR6")).toBeFocused();
  await page.keyboard.press("Shift+F10");
  await expect(menu).toBeVisible();
  await page.keyboard.press("Escape");
  expect(writes.crowns).toEqual([]);
  expect(writes.other).toEqual([]);
});

test("previously recorded fractured crowns remain visible without offering new standalone fracture authoring", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "Legacy crown fracture inspection");
  const empty = await snapshot(request, patientId, headers);
  await page.route(`**${toothPath(patientId)}`, async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    await route.fulfill({ json: { ...empty, teeth: { UR3: {
      condition: null, movement: null, rotation: null, revision: 1,
      root_observations: {}, crown_observation: { kind: "fractured", issues: [] },
      bridge_group_id: null, bridge_role: null, updated_at: null, updated_by: null,
    } } } });
  });
  await openChart(page, patientId);
  const writes = observeWrites(page, patientId);
  await crownDrawing(page, "UR3", { kind: "fractured", issues: [] });
  await expect(page.getByTestId("tooth-root-UR3-1")).toBeAttached();
  await activateCrown(page, "UR3");
  await expect(page.getByTestId("crown-diagnosis-palette-fractured")).toHaveCount(0);
  const menu = await openCrownMenu(page, "UR3");
  await expect(menu.getByTestId("clinical-crown-condition-fractured")).toHaveCount(0);
  await expect(menu).toContainText(/broken[- ]away|fractured/i);
  await expect(menu.getByTestId("clinical-crown-apply")).toBeDisabled();
  await page.keyboard.press("Escape");
  await page.reload({ waitUntil: "domcontentloaded" });
  await ready(page);
  await crownDrawing(page, "UR3", { kind: "fractured", issues: [] });
  expect(writes.crowns).toEqual([]);
  expect(writes.other).toEqual([]);
  expect((await snapshot(request, patientId, headers)).teeth).toEqual({});
});

test("multi-crown Apply records six kinds and combined issues without shrinking roots or billing", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "Crown batch conditions");
  const originalFinance = await readJson(request, `/api/patients/${patientId}/finance-summary`, headers);
  await openChart(page, patientId);
  const writes = observeWrites(page, patientId);
  const originalBox = await page.getByTestId("tooth-svg-UR6").boundingBox();
  let revision = 0;
  for (const kind of crownKinds) {
    const issues: CrownIssue[] = kind === "metal" ? ["decayed", "defective"] : kind === "gold" ? ["fractured", "poor_fitting"] : kind === "porcelain" ? [...crownIssues] : kind === "porcelain_bonded" ? ["defective", "poor_fitting"] : [];
    await selectCrowns(page, kind, ["UR6", "LR6"], issues);
    if (revision === 0) {
      await page.getByTestId("clinical-crown-UR5").click();
      await page.getByTestId("clinical-crown-UR5").click();
      await expect(page.getByTestId("clinical-crown-UR5")).toHaveAttribute("data-crown-selected", "false");
      expect((await snapshot(request, patientId, headers)).teeth).toEqual({});
      expect(writes.crowns).toEqual([]);
    }
    expectMutation(await applyCrown(page, patientId), { teeth: ["UR6", "LR6"], kind, issues, expected_revisions: { UR6: revision, LR6: revision } });
    revision += 1;
    const stored = await snapshot(request, patientId, headers);
    expect(Object.keys(stored.teeth).sort()).toEqual(["LR6", "UR6"]);
    for (const tooth of ["UR6", "LR6"]) {
      expect(stored.teeth[tooth]).toMatchObject({ condition: null, revision, crown_observation: { kind, issues: [...issues].sort() }, root_observations: {} });
      await crownDrawing(page, tooth, { kind, issues });
    }
    await expect(page.locator('[data-testid^="tooth-root-UR6-"]')).toHaveCount(3);
    await expect(page.locator('[data-testid^="tooth-root-LR6-"]')).toHaveCount(2);
    await crownDrawing(page, "UR5", null);
    const box = await page.getByTestId("tooth-svg-UR6").boundingBox();
    expect(box!.width).toBeCloseTo(originalBox!.width, 1);
    expect(box!.height).toBeCloseTo(originalBox!.height, 1);
    await expect(page.locator('[data-crown-selected="true"]')).toHaveCount(0);
  }
  await page.reload({ waitUntil: "domcontentloaded" });
  await ready(page);
  await crownDrawing(page, "UR6", { kind: "composite", issues: [] });
  await crownDrawing(page, "LR6", { kind: "composite", issues: [] });
  const menu = await openCrownMenu(page, "UR6");
  await expect(menu).toContainText(/not specified|unspecified/i);
  for (const issue of crownIssues) await expect(menu.getByTestId(`clinical-crown-issue-${issue}`)).not.toBeChecked();
  expect(writes.crowns).toHaveLength(6);
  expect(writes.other).toEqual([]);
  expect(await readJson(request, `/api/patients/${patientId}/finance-summary`, headers)).toEqual(originalFinance);
  expect(await readJson(request, `/api/patients/${patientId}/clinical/summary`, headers)).toMatchObject({ recent_procedures: [], treatment_plan_items: [], recent_tooth_notes: [] });
});

test("crown context Apply and notes retain root findings through independent area resets", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "Crown note reset retention");
  const root = await request.post(`${getBaseUrl()}${rootPath(patientId)}`, { headers, data: { teeth: ["UR6"], condition: "filled_sound", apicectomy: true, expected_revisions: { UR6: 0 } } });
  expect(root.ok()).toBeTruthy();
  await openChart(page, patientId);
  const menu = await openCrownMenu(page, "UR6");
  await menu.getByTestId("clinical-crown-condition-metal").click();
  await menu.getByTestId("clinical-crown-issue-poor_fitting").check();
  expectMutation(await applyCrown(page, patientId, true), { teeth: ["UR6"], kind: "metal", issues: ["poor_fitting"], expected_revisions: { UR6: 1 } });
  await crownDrawing(page, "UR6", { kind: "metal", issues: ["poor_fitting"] });
  await expect(page.locator('[data-testid^="clinical-root-finding-UR6-"]')).toHaveCount(3);
  await selectCrowns(page, "gold", ["UR6", "LR6"]);
  await expect(page.getByTestId("crown-diagnosis-note")).toBeDisabled();
  await page.getByTestId("clinical-crown-LR6").click();
  await expect(page.getByTestId("crown-diagnosis-note")).toBeEnabled();
  await page.getByTestId("crown-diagnosis-note").click();
  await expect(page.getByTestId("patient-chart-note-body")).toBeFocused();
  const noteText = "Synthetic crown observation note retained through independent resets";
  await page.getByTestId("patient-chart-note-body").fill(noteText);
  const noteSave = nextSave(page, `/api/patients/${patientId}/tooth-notes`);
  await page.getByTestId("patient-chart-note-add").click();
  const noteResponse = await noteSave;
  expect(noteResponse.ok()).toBeTruthy();
  expect(noteResponse.request().postDataJSON()).toEqual({ tooth: "UR6", surface: null, note: noteText });
  await expect(page.getByTestId("tooth-note-flag-UR6")).toBeVisible();
  expect((await snapshot(request, patientId, headers)).teeth.UR6.crown_observation).toEqual({ kind: "metal", issues: ["poor_fitting"] });
  const historyBefore = await readJson(request, `/api/patients/${patientId}/tooth-history?tooth=UR6`, headers);
  await selectCrowns(page, "reset", ["UR6"]);
  expectMutation(await applyCrown(page, patientId), { teeth: ["UR6"], kind: null, issues: [], expected_revisions: { UR6: 2 } });
  await crownDrawing(page, "UR6", { kind: null, issues: [] });
  await expect(page.locator('[data-testid^="clinical-root-finding-UR6-"]')).toHaveCount(3);
  await selectCrowns(page, "gold", ["UR6"], ["defective"]);
  await applyCrown(page, patientId);
  await page.getByTestId("clinical-root-UR6").click({ button: "right" });
  const rootReset = nextSave(page, rootPath(patientId));
  await page.getByTestId("clinical-root-reset").click();
  expect((await rootReset).ok()).toBeTruthy();
  await expect(page.locator('[data-testid^="clinical-root-finding-UR6-"]')).toHaveCount(0);
  await crownDrawing(page, "UR6", { kind: "gold", issues: ["defective"] });
  await page.reload({ waitUntil: "domcontentloaded" });
  await ready(page);
  await crownDrawing(page, "UR6", { kind: "gold", issues: ["defective"] });
  await page.getByTestId("tooth-label-UR6").click({ button: "right" });
  const toothReset = nextSave(page, toothPath(patientId));
  await page.getByTestId("clinical-baseline-condition-reset").click();
  expect((await toothReset).ok()).toBeTruthy();
  expect((await snapshot(request, patientId, headers)).teeth.UR6).toMatchObject({ condition: "unrecorded", crown_observation: null, root_observations: {} });
  await crownDrawing(page, "UR6", null);
  await expect(page.getByTestId("tooth-note-flag-UR6")).toBeVisible();
  expect(await readJson(request, `/api/patients/${patientId}/tooth-history?tooth=UR6`, headers)).toEqual(historyBefore);
});

test("stale crown batches are atomic and shared revisions protect crowns from root resets", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "Crown atomic conflict");
  await openChart(page, patientId);
  await selectCrowns(page, "metal", ["UR6", "LR6"], ["decayed"]);
  const external = await request.post(`${getBaseUrl()}${rootPath(patientId)}`, { headers, data: { teeth: ["UR6"], condition: "filled_sound", expected_revisions: { UR6: 0 } } });
  expect(external.ok()).toBeTruthy();
  const conflict = nextSave(page, crownPath(patientId));
  await page.getByTestId("crown-diagnosis-apply").click();
  const response = await conflict;
  expect(response.status()).toBe(409);
  expectMutation(response.request().postDataJSON() as CrownMutation, { teeth: ["UR6", "LR6"], kind: "metal", issues: ["decayed"], expected_revisions: { UR6: 0, LR6: 0 } });
  await expect(page.getByTestId("clinical-baseline-error")).toContainText(/changed.*Refresh/i);
  const failed = await snapshot(request, patientId, headers);
  expect(Object.keys(failed.teeth)).toEqual(["UR6"]);
  expect(failed.teeth.UR6).toMatchObject({ revision: 1, crown_observation: null });
  await crownDrawing(page, "LR6", null);
  await page.getByRole("button", { name: "Refresh conditions", exact: true }).click();
  await ready(page);
  await expect(page.locator('[data-testid^="clinical-root-finding-UR6-"]')).toHaveCount(3);
  await recordCrown(request, patientId, headers, { teeth: ["UR6"], kind: "gold", issues: ["fractured"], expected_revisions: { UR6: 1 } });
  await page.getByTestId("clinical-root-UR6").click({ button: "right" });
  const rootConflict = nextSave(page, rootPath(patientId));
  await page.getByTestId("clinical-root-reset").click();
  expect((await rootConflict).status()).toBe(409);
  await expect(page.getByTestId("clinical-baseline-error")).toContainText(/changed.*Refresh/i);
  expect((await snapshot(request, patientId, headers)).teeth.UR6).toMatchObject({ revision: 2, crown_observation: { kind: "gold", issues: ["fractured"] } });
  await page.getByRole("button", { name: "Refresh conditions", exact: true }).click();
  await ready(page);
  await crownDrawing(page, "UR6", { kind: "gold", issues: ["fractured"] });
  await expect(page.locator('[data-testid^="clinical-root-finding-UR6-"]')).toHaveCount(3);
});

test("missing and unerupted teeth cannot accept crowns while implant crowns and read-only inspection remain safe", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "Crown access boundaries");
  for (const [tooth, condition] of [["UR5", "missing"], ["UL5", "unerupted"], ["LR5", "implant"]]) {
    const response = await request.post(`${getBaseUrl()}${toothPath(patientId)}`, { headers, data: { teeth: [tooth], condition, expected_revisions: { [tooth]: 0 } } });
    expect(response.ok()).toBeTruthy();
  }
  await openChart(page, patientId);
  await expect(page.getByRole("button", { name: "UR5 crown area", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "UL5 crown area", exact: true })).toHaveCount(0);
  await selectCrowns(page, "porcelain", ["LR5"]);
  expectMutation(await applyCrown(page, patientId), { teeth: ["LR5"], kind: "porcelain", issues: [], expected_revisions: { LR5: 1 } });
  await expect(page.getByTestId("tooth-baseline-implant-LR5")).toBeAttached();
  await crownDrawing(page, "LR5", { kind: "porcelain", issues: [] });
  await page.route("**/api/me/capabilities", (route) => route.fulfill({ json: ["patients.view", "clinical.view"] }));
  await openChart(page, patientId);
  const writes = observeWrites(page, patientId);
  await expect(page.getByTestId("patient-clinical-section")).toHaveAttribute("data-clinical-mode", "read-only");
  await activateCrown(page, "LR5");
  for (const kind of [...crownKinds, "reset", "denture_cocr", "denture_acrylic"]) await expect(page.getByTestId(`crown-diagnosis-palette-${kind}`)).toBeDisabled();
  await expect(page.getByTestId("crown-diagnosis-apply")).toBeDisabled();
  await expect(page.getByTestId("crown-diagnosis-note")).toBeDisabled();
  const menu = await openCrownMenu(page, "LR5");
  for (const kind of crownKinds) await expect(menu.getByTestId(`clinical-crown-condition-${kind}`)).toBeDisabled();
  await expect(menu.getByTestId("clinical-crown-apply")).toBeDisabled();
  await expect(menu.getByTestId("clinical-crown-reset")).toBeDisabled();
  expect(writes.crowns).toEqual([]);
  expect(writes.other).toEqual([]);
});

test("pending and failed crown saves block other mutations without drawing unsaved findings", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "Crown failed save safety");
  await openChart(page, patientId);
  const writes = observeWrites(page, patientId);
  let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route(`**${crownPath(patientId)}`, async (route) => {
    await gate;
    await route.fulfill({ status: 500, contentType: "text/html", body: "<html>synthetic private crown infrastructure diagnostic</html>" });
  });
  await selectCrowns(page, "gold", ["UR6", "LR6"], ["defective"]);
  const response = nextSave(page, crownPath(patientId));
  try {
    await page.getByTestId("crown-diagnosis-apply").click();
    await expect(page.getByTestId("clinical-baseline-status")).toContainText(/saving/i);
    for (const id of ["crown-diagnosis-apply", "diagnosis-level-tooth", "crown-diagnosis-cancel", "crown-diagnosis-palette-metal"]) await expect(page.getByTestId(id)).toBeDisabled();
    await page.getByTestId("clinical-root-UR6").click({ button: "right" });
    await expect(page.getByTestId("clinical-root-action-menu")).toHaveCount(0);
    await page.getByTestId("clinical-crown-UR6").click({ button: "right" });
    await expect(page.getByTestId("clinical-crown-action-menu")).toHaveCount(0);
    await crownDrawing(page, "UR6", null);
    await crownDrawing(page, "LR6", null);
    expect(writes.crowns).toHaveLength(1);
    expect(writes.other).toEqual([]);
    expect((await snapshot(request, patientId, headers)).teeth).toEqual({});
  } finally { release(); }
  expect((await response).status()).toBe(500);
  await expect(page.getByTestId("clinical-baseline-error")).toContainText(/could not be confirmed/i);
  await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/saved/i);
  await expect(page.getByText("synthetic private crown infrastructure diagnostic")).toHaveCount(0);
  expect((await snapshot(request, patientId, headers)).teeth).toEqual({});
  await page.unroute(`**${crownPath(patientId)}`);
  await page.getByRole("button", { name: "Refresh conditions", exact: true }).click();
  await ready(page);
  await page.getByTestId("crown-diagnosis-cancel").click();
  await selectCrowns(page, "gold", ["UR6", "LR6"], ["defective"]);
  expectMutation(await applyCrown(page, patientId), { teeth: ["UR6", "LR6"], kind: "gold", issues: ["defective"], expected_revisions: { UR6: 0, LR6: 0 } });
  await crownDrawing(page, "UR6", { kind: "gold", issues: ["defective"] });
  expect(writes.crowns).toHaveLength(2);
});

test("crown draft cancellation and patient tab mode or surface switches never save implicitly", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "Crown draft boundaries");
  await openChart(page, patientId);
  const writes = observeWrites(page, patientId);
  await selectCrowns(page, "metal", ["UR6", "LR6"], ["decayed"]);
  await page.getByTestId("crown-diagnosis-cancel").click();
  await expect(page.getByTestId("clinical-crown-diagnosis-palette")).toBeVisible();
  await expect(page.locator('[data-crown-selected="true"]')).toHaveCount(0);
  await expect(page.getByTestId("crown-diagnosis-apply")).toBeDisabled();
  await selectCrowns(page, "gold", ["UR6"]);
  await page.getByTestId("diagnosis-level-tooth").click();
  await expect(page.getByTestId("clinical-diagnosis-palette")).toBeVisible();
  for (const tooth of ["UR6", "LR6"]) {
    await selectCrowns(page, "gold", ["UR6", "LR6"]);
    await page.getByTestId(`tooth-surface-${tooth}-M`).click({ button: "right" });
    await expect(page.getByTestId("clinical-surface-diagnosis-palette")).toBeVisible();
    await expect(page.getByTestId("clinical-diagnosis-palette")).toHaveCount(0);
    await expect(page.getByTestId("clinical-surface-apply")).toBeDisabled();
    await expect(page.getByTestId("clinical-crown-diagnosis-palette")).toHaveCount(0);
    await expect(page.locator('[data-crown-selected="true"]')).toHaveCount(0);
    await page.keyboard.press("Escape");
  }
  for (const mode of ["planned", "history"]) {
    await selectCrowns(page, "gold", ["UR6"]);
    await page.getByTestId(`clinical-chart-view-${mode}`).click();
    await expect(page.getByTestId("clinical-crown-diagnosis-palette")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "UR6 crown area", exact: true })).toHaveCount(0);
    await page.getByTestId("clinical-chart-view-current").click();
    await ready(page);
    await expect(page.getByTestId("clinical-diagnosis-palette")).toBeVisible();
  }
  await selectCrowns(page, "gold", ["UR6"]);
  await page.getByTestId("patient-tab-Personal").click();
  await expect(page.getByTestId("clinical-crown-diagnosis-palette")).toHaveCount(0);
  await openChart(page, patientId);
  await selectCrowns(page, "gold", ["UR6"]);
  const otherId = await createPatient(request, { first_name: "Synthetic", last_name: `Crown next patient ${Date.now()}` });
  await openChart(page, otherId);
  await expect(page.getByTestId("clinical-crown-diagnosis-palette")).toHaveCount(0);
  await expect(page.locator('[data-crown-selected="true"]')).toHaveCount(0);
  expect((await snapshot(request, patientId, headers)).teeth).toEqual({});
  expect((await snapshot(request, otherId, headers)).teeth).toEqual({});
  expect(writes.crowns).toEqual([]);
  expect(writes.other).toEqual([]);
});

test("crown findings and combined-issue choices remain legible in light dark and mobile previews", async ({ page, request }, testInfo) => {
  const { patientId, headers } = await setup(page, request, "Crown visual preview");
  const fixtures: Array<{ tooth: string; kind: CrownKind; issues: CrownIssue[] }> = [
    { tooth: "UR6", kind: "metal", issues: ["decayed", "defective"] },
    { tooth: "UR3", kind: "porcelain_bonded", issues: [] },
    { tooth: "UL3", kind: "missing", issues: [] },
    { tooth: "UL6", kind: "gold", issues: ["poor_fitting"] },
    { tooth: "LR6", kind: "porcelain", issues: [] },
    { tooth: "LL6", kind: "composite", issues: ["fractured"] },
  ];
  for (const { tooth, kind, issues } of fixtures) await recordCrown(request, patientId, headers, { teeth: [tooth], kind, issues, expected_revisions: { [tooth]: 0 } });
  await openChart(page, patientId);
  const writes = observeWrites(page, patientId);
  for (const { tooth, kind, issues } of fixtures) await crownDrawing(page, tooth, { kind, issues });
  await selectCrowns(page, "metal", ["UR6", "LR6"], ["decayed", "defective"]);
  const capture = async (name: string) => {
    await page.evaluate(() => { window.scrollTo(0, 0); return new Promise<void>((resolve) => requestAnimationFrame(() => resolve())); });
    const path = testInfo.outputPath(`${name}.png`);
    await page.screenshot({ path, fullPage: true });
    await testInfo.attach(name, { path, contentType: "image/png" });
  };
  await capture("crown-diagnosis-light");
  await page.getByRole("button", { name: "Toggle theme", exact: true }).click();
  await capture("crown-diagnosis-dark");
  const menu = await openCrownMenu(page, "UR6");
  await expect(menu.getByTestId("clinical-crown-issue-decayed")).toBeChecked();
  await expect(menu.getByTestId("clinical-crown-issue-defective")).toBeChecked();
  await expect(menu.getByTestId("clinical-crown-condition-metal")).toHaveCSS("font-size", "18px");
  await expect(menu.getByTestId("clinical-crown-condition-metal")).toHaveCSS("gap", "10px");
  const darkMenu = testInfo.outputPath("crown-diagnosis-dark-menu.png");
  await page.screenshot({ path: darkMenu });
  await testInfo.attach("crown-diagnosis-dark-menu", { path: darkMenu, contentType: "image/png" });
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Toggle theme", exact: true }).click();
  await page.getByTestId("crown-diagnosis-cancel").click();
  await selectCrowns(page, "metal", ["UR6", "LR6"], ["decayed", "defective"]);
  await page.setViewportSize({ width: 1900, height: 2100 });
  await capture("crown-diagnosis-wide");
  const chart = await page.getByTestId("clinical-chart").boundingBox();
  const palette = await page.getByTestId("clinical-crown-diagnosis-palette").boundingBox();
  expect(chart).not.toBeNull();
  expect(palette).not.toBeNull();
  const x = Math.max(0, Math.min(chart!.x, palette!.x) - 10);
  const y = Math.max(0, chart!.y - 10);
  const right = Math.max(chart!.x + chart!.width, palette!.x + palette!.width) + 10;
  const bottom = palette!.y + palette!.height + 10;
  expect(right).toBeLessThanOrEqual(1900);
  expect(bottom).toBeLessThanOrEqual(2100);
  const closeup = testInfo.outputPath("crown-diagnosis-chart-palette-closeup.png");
  await page.screenshot({ path: closeup, clip: { x, y, width: right - x, height: bottom - y } });
  await testInfo.attach("crown-diagnosis-chart-palette-closeup", { path: closeup, contentType: "image/png" });
  await page.setViewportSize({ width: 390, height: 844 });
  await openCrownMenu(page, "UR6");
  const bounds = await menu.boundingBox();
  expect(bounds).not.toBeNull();
  expect(bounds!.x).toBeGreaterThanOrEqual(0);
  expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(390);
  expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(844);
  await menu.getByTestId("clinical-crown-apply").scrollIntoViewIfNeeded();
  await expect(menu.getByTestId("clinical-crown-apply")).toBeVisible();
  const mobileMenu = testInfo.outputPath("crown-diagnosis-mobile-menu.png");
  await page.screenshot({ path: mobileMenu });
  await testInfo.attach("crown-diagnosis-mobile-menu", { path: mobileMenu, contentType: "image/png" });
  await page.keyboard.press("Escape");
  await capture("crown-diagnosis-mobile");
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(391);
  expect(writes.crowns).toEqual([]);
  expect(writes.other).toEqual([]);
});
