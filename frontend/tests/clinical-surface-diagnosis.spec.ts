import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

type Observation = { kind: "carious" | "defective" | "restored" | "sealant" | null; material: string | null; condition: string | null; defects: string[] };
type Target = { tooth: string; surfaces: string[] };
type Mutation = { targets: Target[]; observation: Observation; expected_revisions: Record<string, number> };
type Snapshot = { teeth: Record<string, { revision: number; condition: string | null; surface_observations: Record<string, Observation>; root_observations: Record<string, unknown>; crown_observation: unknown }>; note_teeth: string[] };
const kinds = ["carious", "defective", "restored", "sealant", "reset"] as const;
const blank: Observation = { kind: null, material: null, condition: null, defects: [] };
const gold: Observation = { kind: "restored", material: "gold", condition: null, defects: [] };
const path = (id: string, action = "tooth-conditions") => `/api/patients/${id}/clinical/${action}`;

async function setup(page: Page, request: APIRequestContext, name: string) {
  const token = await primePageAuth(page, request);
  const patientId = await createPatient(request, { first_name: "Synthetic", last_name: `Surface ${name} ${Date.now()}` });
  await page.setViewportSize({ width: 1600, height: 1150 });
  return { patientId, headers: { Authorization: `Bearer ${token}` } };
}
async function read(request: APIRequestContext, url: string, headers: Record<string, string>) {
  const response = await request.get(`${getBaseUrl()}${url}`, { headers });
  expect(response.ok()).toBeTruthy();
  return response.json();
}
async function snapshot(request: APIRequestContext, id: string, headers: Record<string, string>): Promise<Snapshot> {
  return read(request, path(id), headers);
}
async function post(request: APIRequestContext, url: string, headers: Record<string, string>, data: unknown) {
  const response = await request.post(`${getBaseUrl()}${url}`, { headers, data });
  expect(response.ok()).toBeTruthy();
  return response.json();
}
async function ready(page: Page) {
  await expect(page.getByTestId("clinical-chart")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("clinical-baseline-status")).not.toContainText(/loading|saving/i, { timeout: 30_000 });
}
async function open(page: Page, id: string) {
  await page.goto(`${getBaseUrl()}/patients/${id}/clinical?clinicalView=current`, { waitUntil: "domcontentloaded" });
  await ready(page);
}
async function select(page: Page, targets: Target[]) {
  for (const { tooth, surfaces } of targets) for (const surface of surfaces) {
    await page.getByTestId(`clinical-surface-${tooth}-${surface}`).click();
    await expect(page.getByTestId(`clinical-surface-${tooth}-${surface}`)).toHaveAttribute("aria-pressed", "true");
  }
  await expect(page.getByTestId("clinical-surface-diagnosis-palette")).toBeVisible();
}
function nextSave(page: Page, id: string) {
  return page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === path(id, "surface-conditions"));
}
async function apply(page: Page, id: string, menu = false) {
  const pending = nextSave(page, id);
  await page.getByTestId(menu ? "clinical-surface-apply" : "surface-diagnosis-apply").click();
  const response = await pending;
  expect(response.ok()).toBeTruthy();
  await ready(page);
  return response.request().postDataJSON() as Mutation;
}
function equalMutation(actual: Mutation, expected: Mutation) {
  const normalized = (value: Mutation) => ({ ...value, targets: value.targets.map((target) => ({ ...target, surfaces: [...target.surfaces].sort() })).sort((a, b) => a.tooth.localeCompare(b.tooth)) });
  expect(normalized(actual)).toEqual(normalized(expected));
}
async function drawing(page: Page, tooth: string, surface: string, observation: Observation | null) {
  const target = page.getByTestId(`clinical-surface-${tooth}-${surface}`);
  await expect(target).toHaveAttribute("data-surface-kind", observation ? observation.kind ?? "unspecified" : "untouched");
  await expect(target).toHaveAttribute("data-surface-recorded", String(observation !== null));
  await expect(page.getByTestId(`clinical-surface-finding-${tooth}-${surface}`)).toHaveCount(observation ? 1 : 0);
  if (observation?.material) await expect(target).toHaveAttribute("data-surface-material", observation.material);
  else await expect(target).not.toHaveAttribute("data-surface-material");
  if (observation?.condition) await expect(target).toHaveAttribute("data-surface-condition", observation.condition);
  else await expect(target).not.toHaveAttribute("data-surface-condition");
}
function writes(page: Page, id: string) {
  const surfaces: Mutation[] = [];
  const other: string[] = [];
  page.on("request", (request) => {
    if (!["POST", "PUT", "PATCH", "DELETE"].includes(request.method())) return;
    const url = new URL(request.url()).pathname;
    if (url === path(id, "surface-conditions")) surfaces.push(request.postDataJSON());
    else if (/\/api\/(?:patients|invoices|payments|treatment)/.test(url)) other.push(url);
  });
  return { surfaces, other };
}

test("surface palette and keyboard context menu preserve selections with honest unspecified defaults", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "controls");
  await open(page, patientId);
  const observed = writes(page, patientId);
  await select(page, [{ tooth: "UR6", surfaces: ["M", "O", "D"] }]);
  await expect(page.getByTestId("clinical-diagnosis-palette")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Close tooth tools", exact: true })).toHaveCount(0);
  await expect(page.getByTestId("surface-diagnosis-selection")).toContainText("UR6 MOD");
  await expect(page.getByTestId("surface-diagnosis-apply")).toBeDisabled();
  for (const kind of kinds) await expect(page.getByTestId(`surface-diagnosis-palette-${kind}`)).toHaveCount(1);
  await page.getByTestId("surface-diagnosis-palette-carious").click();
  await expect(page.getByRole("combobox", { name: "Caries stage", exact: true })).toHaveValue("");
  await page.getByTestId("surface-diagnosis-stage").selectOption("carious_established");
  await page.getByTestId("surface-diagnosis-palette-restored").click();
  await expect(page.getByRole("combobox", { name: "Restoration material", exact: true })).toHaveValue("unknown");
  await expect(page.getByRole("combobox", { name: "Surface condition", exact: true })).toHaveValue("");
  await expect(page.getByTestId("surface-diagnosis-material").locator('option:not([disabled])')).toHaveCount(13);
  await page.getByTestId("surface-diagnosis-condition").selectOption("defective");
  await page.getByTestId("surface-diagnosis-defect-overhang").check();
  await page.getByTestId("surface-diagnosis-condition").selectOption("sound");
  await page.getByTestId("surface-diagnosis-condition").selectOption("defective");
  await expect(page.getByTestId("surface-diagnosis-defect-overhang")).not.toBeChecked();
  const trigger = page.getByTestId("clinical-surface-UR6-O");
  await trigger.focus();
  await page.keyboard.press("Shift+F10");
  const menu = page.getByTestId("clinical-surface-action-menu");
  await expect(menu).toHaveRole("dialog");
  await expect(menu).toHaveAccessibleName("Surface actions for UR6 MOD");
  await expect(menu.getByRole("menu", { name: "Surface category" })).toBeVisible();
  await expect(menu.getByTestId("clinical-surface-selection")).toContainText("UR6 MOD");
  await expect(menu.getByTestId("clinical-surface-apply")).toHaveText("Apply to 3 surfaces");
  await menu.getByTestId("clinical-surface-condition-sealant").click();
  await expect(menu.getByTestId("clinical-surface-condition")).toHaveValue("");
  await expect(page.getByTestId("clinical-chart-menu-add-procedure")).toHaveCount(0);
  await expect(page.getByTestId("clinical-chart-menu-add-plan")).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(menu).toHaveCount(0);
  await expect(trigger).toBeFocused();
  await trigger.press("Space");
  await expect(trigger).toHaveAttribute("aria-pressed", "false");
  await trigger.press("Enter");
  await expect(trigger).toHaveAttribute("aria-pressed", "true");
  expect(observed.surfaces).toEqual([]);
  expect(observed.other).toEqual([]);
  expect((await snapshot(request, patientId, headers)).teeth).toEqual({});
});

test("MOD and MIDBP atomic saves and selected-surface reset preserve roots crowns notes and finance", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "preservation");
  await post(request, path(patientId, "root-conditions"), headers, { teeth: ["UR6"], condition: "filled_sound", apicectomy: true, expected_revisions: { UR6: 0 } });
  await post(request, path(patientId, "crown-conditions"), headers, { teeth: ["UR6"], kind: "porcelain_bonded", issues: ["defective"], expected_revisions: { UR6: 1 } });
  await post(request, `/api/patients/${patientId}/tooth-notes`, headers, { tooth: "UR6", surface: null, note: "Synthetic surface preservation note" });
  const before = await snapshot(request, patientId, headers);
  const finance = await read(request, `/api/patients/${patientId}/finance-summary`, headers);
  const history = await read(request, `/api/patients/${patientId}/tooth-history?tooth=UR6`, headers);
  await open(page, patientId);
  const observed = writes(page, patientId);
  const targets = [{ tooth: "UR6", surfaces: ["M", "O", "D"] }, { tooth: "UL3", surfaces: ["M", "I", "D", "B", "P"] }];
  await select(page, targets);
  await page.getByTestId("surface-diagnosis-palette-restored").click();
  await page.getByTestId("surface-diagnosis-material").selectOption("gold");
  await expect(page.getByTestId("surface-diagnosis-note")).toBeDisabled();
  await expect(page.getByTestId("surface-diagnosis-apply")).toHaveText("Apply to 8 surfaces");
  equalMutation(await apply(page, patientId), { targets, observation: gold, expected_revisions: { UR6: 2, UL3: 0 } });
  let stored = await snapshot(request, patientId, headers);
  expect(stored.teeth.UR6.revision).toBe(3);
  expect(stored.teeth.UL3.revision).toBe(1);
  for (const { tooth, surfaces } of targets) for (const surface of surfaces) {
    expect(stored.teeth[tooth].surface_observations[surface]).toEqual(gold);
    await drawing(page, tooth, surface, gold);
  }
  await page.reload({ waitUntil: "domcontentloaded" });
  await ready(page);
  await select(page, [{ tooth: "UR6", surfaces: ["O"] }]);
  await page.getByTestId("surface-diagnosis-palette-reset").click();
  await expect(page.getByTestId("surface-diagnosis-selection")).toContainText("Resets only the selected surfaces");
  equalMutation(await apply(page, patientId), { targets: [{ tooth: "UR6", surfaces: ["O"] }], observation: blank, expected_revisions: { UR6: 3 } });
  await drawing(page, "UR6", "O", blank);
  await drawing(page, "UR6", "M", gold);
  await drawing(page, "UR6", "D", gold);
  await page.getByTestId("clinical-surface-UR6-M").click({ button: "right" });
  const edit = page.getByTestId("clinical-surface-action-menu");
  await expect(edit.getByTestId("clinical-surface-condition-restored")).toHaveAttribute("aria-checked", "true");
  await expect(edit.getByTestId("clinical-surface-material")).toHaveValue("gold");
  await expect(edit.getByTestId("clinical-surface-condition")).toHaveValue("");
  await edit.getByTestId("clinical-surface-condition").selectOption("sound");
  equalMutation(await apply(page, patientId, true), { targets: [{ tooth: "UR6", surfaces: ["M"] }], observation: { ...gold, condition: "sound" }, expected_revisions: { UR6: 4 } });
  await drawing(page, "UR6", "M", { ...gold, condition: "sound" });
  await drawing(page, "UR6", "D", gold);
  stored = await snapshot(request, patientId, headers);
  expect(stored.teeth.UR6.root_observations).toEqual(before.teeth.UR6.root_observations);
  expect(stored.teeth.UR6.crown_observation).toEqual(before.teeth.UR6.crown_observation);
  expect(stored.teeth.UR6.condition).toEqual(before.teeth.UR6.condition);
  await expect(page.getByTestId("tooth-note-flag-UR6")).toBeVisible();
  expect(await read(request, `/api/patients/${patientId}/finance-summary`, headers)).toEqual(finance);
  expect(await read(request, `/api/patients/${patientId}/tooth-history?tooth=UR6`, headers)).toEqual(history);
  expect(observed.surfaces).toHaveLength(3);
  expect(observed.other).toEqual([]);
});

test("caries stages defects restorations and sealants retain exact independent observations", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "categories");
  await open(page, patientId);
  const cases: Array<{ tooth: string; surface: string; observation: Observation }> = [
    { tooth: "UR6", surface: "M", observation: { ...blank, kind: "carious" } },
    { tooth: "UR6", surface: "O", observation: { ...blank, kind: "carious", condition: "carious_early" } },
    { tooth: "UR6", surface: "D", observation: { ...blank, kind: "carious", condition: "carious_arrested" } },
    { tooth: "UR6", surface: "B", observation: { ...blank, kind: "carious", condition: "carious_established" } },
    { tooth: "UR6", surface: "P", observation: { ...blank, kind: "defective", condition: "defective", defects: ["cracked", "leaking"] } },
    { tooth: "LR6", surface: "O", observation: { ...blank, kind: "restored", material: "unknown" } },
    { tooth: "LL6", surface: "O", observation: { ...blank, kind: "sealant", condition: "sound" } },
  ];
  const revisions: Record<string, number> = {};
  for (const { tooth, surface, observation } of cases) {
    await page.getByTestId(`clinical-surface-${tooth}-${surface}`).click({ button: "right" });
    const menu = page.getByTestId("clinical-surface-action-menu");
    await menu.getByTestId(`clinical-surface-condition-${observation.kind}`).click();
    if (observation.kind === "carious" && observation.condition) await menu.getByTestId("clinical-surface-stage").selectOption(observation.condition);
    if (observation.kind === "sealant") await menu.getByTestId("clinical-surface-condition").selectOption("sound");
    for (const defect of observation.defects) await menu.getByTestId(`clinical-surface-defect-${defect}`).check();
    equalMutation(await apply(page, patientId, true), { targets: [{ tooth, surfaces: [surface] }], observation, expected_revisions: { [tooth]: revisions[tooth] ?? 0 } });
    revisions[tooth] = (revisions[tooth] ?? 0) + 1;
    await drawing(page, tooth, surface, observation);
    if (observation.kind === "carious") await expect(page.getByTestId(`clinical-surface-pattern-${tooth}-${surface}`)).toHaveAttribute("data-stage", observation.condition?.replace("carious_", "") ?? "unspecified");
    if (observation.kind === "defective") await expect(page.getByTestId(`clinical-surface-pattern-${tooth}-${surface}`)).toHaveAttribute("data-pattern", "defective");
  }
  await page.reload({ waitUntil: "domcontentloaded" });
  await ready(page);
  const stored = await snapshot(request, patientId, headers);
  for (const { tooth, surface, observation } of cases) {
    expect(stored.teeth[tooth].surface_observations[surface]).toEqual(observation);
    await drawing(page, tooth, surface, observation);
  }
});

test("surface geometry places mesial toward the midline and names palatal lingual incisal correctly", async ({ page, request }) => {
  const { patientId } = await setup(page, request, "orientation");
  await open(page, patientId);
  for (const tooth of ["UR6", "UL6", "LR6", "LL6"]) {
    const m = await page.getByTestId(`clinical-surface-${tooth}-M`).boundingBox();
    const d = await page.getByTestId(`clinical-surface-${tooth}-D`).boundingBox();
    expect(m).not.toBeNull(); expect(d).not.toBeNull();
    if (tooth[1] === "R") expect(m!.x + m!.width / 2).toBeGreaterThan(d!.x + d!.width / 2);
    else expect(m!.x + m!.width / 2).toBeLessThan(d!.x + d!.width / 2);
    await expect(page.getByTestId(`clinical-surface-${tooth}-${tooth[0] === "U" ? "P" : "L"}`)).toHaveAccessibleName(`${tooth} ${tooth[0] === "U" ? "Palatal" : "Lingual"} surface`);
    await expect(page.getByTestId(`clinical-surface-${tooth}-${tooth[0] === "U" ? "L" : "P"}`)).toHaveCount(0);
  }
  await expect(page.getByTestId("clinical-surface-UL3-I")).toHaveAccessibleName("UL3 Incisal surface");
  await expect(page.getByTestId("clinical-surface-UL3-O")).toHaveCount(0);
  const size = await page.getByTestId("tooth-svg-UR6").boundingBox();
  await select(page, [{ tooth: "UR6", surfaces: ["M", "O", "D"] }]);
  const selectedSize = await page.getByTestId("tooth-svg-UR6").boundingBox();
  expect(selectedSize!.width).toBeCloseTo(size!.width, 1);
  expect(selectedSize!.height).toBeCloseTo(size!.height, 1);
});

test("stale surface batches are atomic and pending failed requests cannot draw or save other findings", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "conflict safety");
  await open(page, patientId);
  const targets = [{ tooth: "UR6", surfaces: ["M", "O"] }, { tooth: "LR6", surfaces: ["O"] }];
  await select(page, targets);
  await page.getByTestId("surface-diagnosis-palette-restored").click();
  await post(request, path(patientId, "root-conditions"), headers, { teeth: ["UR6"], condition: "filled_sound", expected_revisions: { UR6: 0 } });
  const conflict = nextSave(page, patientId);
  await page.getByTestId("surface-diagnosis-apply").click();
  expect((await conflict).status()).toBe(409);
  await expect(page.getByTestId("clinical-baseline-error")).toContainText(/changed.*Refresh/i);
  let stored = await snapshot(request, patientId, headers);
  expect(stored.teeth.UR6.surface_observations).toEqual({});
  expect(stored.teeth.LR6).toBeUndefined();
  await drawing(page, "LR6", "O", null);
  await page.getByRole("button", { name: "Refresh conditions", exact: true }).click();
  await ready(page);
  await page.getByTestId("surface-diagnosis-cancel").click();
  await select(page, targets);
  await page.getByTestId("surface-diagnosis-palette-sealant").click();
  const observed = writes(page, patientId);
  let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route(`**${path(patientId, "surface-conditions")}`, async (route) => {
    await gate;
    await route.fulfill({ status: 500, contentType: "text/html", body: "<html>Synthetic private surface infrastructure diagnostic</html>" });
  });
  const pending = nextSave(page, patientId);
  try {
    await page.getByTestId("surface-diagnosis-apply").click();
    await expect(page.getByTestId("clinical-baseline-status")).toContainText(/saving/i);
    await expect(page.getByTestId("surface-diagnosis-apply")).toBeDisabled();
    await expect(page.getByTestId("surface-diagnosis-palette-reset")).toBeDisabled();
    await page.getByTestId("surface-diagnosis-cancel").click();
    await expect(page.getByTestId("surface-diagnosis-selection")).toContainText("UR6 MO");
    await page.getByTestId("clinical-root-UR6").click({ button: "right" });
    await expect(page.getByTestId("clinical-root-action-menu")).toHaveCount(0);
    await page.getByTestId("clinical-surface-LR6-D").click();
    await expect(page.getByTestId("clinical-surface-LR6-D")).toHaveAttribute("aria-pressed", "false");
    await drawing(page, "UR6", "M", null);
    expect(observed.surfaces).toHaveLength(1);
    expect(observed.other).toEqual([]);
  } finally { release(); }
  expect((await pending).status()).toBe(500);
  await expect(page.getByTestId("clinical-baseline-error")).toContainText(/could not be confirmed/i);
  await expect(page.getByText("Synthetic private surface infrastructure diagnostic")).toHaveCount(0);
  stored = await snapshot(request, patientId, headers);
  expect(stored.teeth.UR6.surface_observations).toEqual({});
  expect(stored.teeth.LR6).toBeUndefined();
  await expect(page.getByTestId("surface-diagnosis-cancel")).toBeEnabled();
});

test("surface eligibility and read-only inspection fail closed without treatment or finance writes", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "permissions");
  for (const [tooth, condition] of [["UR5", "missing"], ["UL5", "unerupted"], ["LR5", "implant"]]) {
    await post(request, path(patientId), headers, { teeth: [tooth], condition, expected_revisions: { [tooth]: 0 } });
  }
  await post(request, path(patientId, "crown-conditions"), headers, { teeth: ["LL5"], kind: "denture_acrylic", issues: [], expected_revisions: { LL5: 0 } });
  await open(page, patientId);
  for (const tooth of ["UR5", "UL5", "LR5", "LL5"]) await expect(page.getByRole("button", { name: `${tooth} Mesial surface`, exact: true })).toHaveCount(0);
  await page.route("**/api/me/capabilities", (route) => route.fulfill({ json: ["patients.view", "clinical.view"] }));
  await open(page, patientId);
  const observed = writes(page, patientId);
  await select(page, [{ tooth: "UR6", surfaces: ["O"] }]);
  for (const kind of kinds) await expect(page.getByTestId(`surface-diagnosis-palette-${kind}`)).toBeDisabled();
  await expect(page.getByTestId("surface-diagnosis-apply")).toBeDisabled();
  await expect(page.getByTestId("surface-diagnosis-note")).toHaveCount(0);
  await page.getByTestId("clinical-surface-UR6-O").click({ button: "right" });
  for (const kind of kinds) await expect(page.getByTestId(`clinical-surface-condition-${kind}`)).toBeDisabled();
  await expect(page.getByTestId("clinical-surface-apply")).toBeDisabled();
  await page.getByTestId("clinical-surface-cancel").click();
  await expect(page.getByTestId("clinical-surface-action-menu")).toHaveCount(0);
  expect(observed.surfaces).toEqual([]); expect(observed.other).toEqual([]);
});

test("surface drafts clear across levels modes tabs patients and single-tooth notes remain tooth-wide", async ({ page, request }) => {
  const { patientId, headers } = await setup(page, request, "boundaries and note");
  await open(page, patientId);
  const observed = writes(page, patientId);
  for (const next of ["clinical-root-UR6", "clinical-crown-UR6", "tooth-label-UR6"]) {
    await select(page, [{ tooth: "UR6", surfaces: ["M", "O"] }]);
    await page.getByTestId("surface-diagnosis-palette-restored").click();
    await page.getByTestId(next).click();
    await expect(page.getByTestId("clinical-surface-diagnosis-palette")).toHaveCount(0);
    await expect(page.locator('.clinical-surface-target[aria-pressed="true"]')).toHaveCount(0);
    await page.keyboard.press("Escape");
  }
  for (const mode of ["planned", "history"]) {
    await select(page, [{ tooth: "UR6", surfaces: ["O"] }]);
    await page.getByTestId("surface-diagnosis-palette-carious").click();
    await page.getByTestId(`clinical-chart-view-${mode}`).click();
    await expect(page.getByTestId("clinical-surface-diagnosis-palette")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "UR6 Occlusal surface", exact: true })).toHaveCount(0);
    await expect(page.getByTestId("tooth-surface-UR6-O")).toBeAttached();
    await page.getByTestId("clinical-chart-view-current").click();
    await ready(page);
    await expect(page.getByTestId("clinical-diagnosis-palette")).toBeVisible();
  }
  await select(page, [{ tooth: "UR6", surfaces: ["M", "O"] }]);
  await page.getByTestId("surface-diagnosis-note").click();
  const note = "Synthetic surface observation note, applies to the whole tooth";
  await page.getByTestId("patient-chart-note-body").fill(note);
  const saved = page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === `/api/patients/${patientId}/tooth-notes`);
  await page.getByTestId("patient-chart-note-add").click();
  const response = await saved;
  expect(response.ok()).toBeTruthy();
  expect(response.request().postDataJSON()).toEqual({ tooth: "UR6", surface: null, note });
  await expect(page.getByTestId("tooth-note-flag-UR6")).toBeVisible();
  await select(page, [{ tooth: "UR6", surfaces: ["D"] }]);
  await page.getByTestId("patient-tab-Personal").click();
  await open(page, patientId);
  await expect(page.getByTestId("clinical-diagnosis-palette")).toBeVisible();
  await select(page, [{ tooth: "UR6", surfaces: ["D"] }]);
  const otherId = await createPatient(request, { first_name: "Synthetic", last_name: `Surface other patient ${Date.now()}` });
  await open(page, otherId);
  await expect(page.getByTestId("clinical-diagnosis-palette")).toBeVisible();
  expect((await snapshot(request, patientId, headers)).teeth).toEqual({});
  expect((await snapshot(request, otherId, headers)).teeth).toEqual({});
  expect(observed.surfaces).toEqual([]);
  expect(observed.other).toEqual([`/api/patients/${patientId}/tooth-notes`]);
});

test("surface findings and multi-surface palette produce clear light dark and mobile previews", async ({ page, request }, testInfo) => {
  const { patientId, headers } = await setup(page, request, "visual preview");
  const fixtures: Array<{ targets: Target[]; observation: Observation }> = [
    { targets: [{ tooth: "UR6", surfaces: ["M", "O", "D"] }], observation: { ...gold, material: "amalgam", condition: "sound" } },
    { targets: [{ tooth: "UL3", surfaces: ["M", "I", "D"] }], observation: gold },
    { targets: [{ tooth: "LR6", surfaces: ["O"] }], observation: { ...blank, kind: "carious", condition: "carious_early" } },
    { targets: [{ tooth: "LR5", surfaces: ["O"] }], observation: { ...blank, kind: "carious", condition: "carious_arrested" } },
    { targets: [{ tooth: "LL6", surfaces: ["M", "O"] }], observation: { ...blank, kind: "carious", condition: "carious_established" } },
    { targets: [{ tooth: "UL6", surfaces: ["O"] }], observation: { ...blank, kind: "sealant", condition: "sound" } },
    { targets: [{ tooth: "LL5", surfaces: ["B"] }], observation: { ...blank, kind: "defective", condition: "defective", defects: ["cracked"] } },
  ];
  for (const fixture of fixtures) await post(request, path(patientId, "surface-conditions"), headers, { ...fixture, expected_revisions: Object.fromEntries(fixture.targets.map(({ tooth }) => [tooth, 0])) });
  await page.setViewportSize({ width: 1900, height: 2300 });
  await open(page, patientId);
  await select(page, [{ tooth: "UR6", surfaces: ["M", "O", "D"] }, { tooth: "UL3", surfaces: ["M", "I", "D", "B", "P"] }]);
  await page.getByTestId("surface-diagnosis-palette-restored").click();
  await page.getByTestId("surface-diagnosis-material").selectOption("gold");
  const palette = page.getByTestId("clinical-surface-diagnosis-palette");
  const icon = palette.locator(".clinical-surface-symbol").first();
  expect(await icon.evaluate((element) => parseFloat(getComputedStyle(element).width))).toBeCloseTo(44.85, 1);
  const top = async () => page.evaluate(async () => { window.scrollTo(0, 0); await new Promise<void>((resolve) => requestAnimationFrame(() => resolve())); });
  await top();
  await page.screenshot({ path: testInfo.outputPath("surface-light.png"), fullPage: true });
  const chartBox = await page.getByTestId("clinical-chart").boundingBox();
  const paletteBox = await palette.boundingBox();
  expect(chartBox).not.toBeNull(); expect(paletteBox).not.toBeNull();
  await page.screenshot({ path: testInfo.outputPath("surface-chart-palette-closeup.png"), clip: { x: Math.min(chartBox!.x, paletteBox!.x), y: chartBox!.y, width: Math.max(chartBox!.width, paletteBox!.width), height: paletteBox!.y + paletteBox!.height - chartBox!.y } });
  await page.getByRole("button", { name: "Toggle theme", exact: true }).click();
  await top();
  await page.screenshot({ path: testInfo.outputPath("surface-dark.png"), fullPage: true });
  await page.getByTestId("clinical-surface-UL3-I").click({ button: "right" });
  const menu = page.getByTestId("clinical-surface-action-menu");
  await expect(menu).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("surface-menu-dark.png") });
  await page.keyboard.press("Escape");
  await page.setViewportSize({ width: 390, height: 844 });
  await palette.scrollIntoViewIfNeeded();
  const menuFree = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
  expect(menuFree).toBeTruthy();
  for (const kind of kinds) {
    const box = await page.getByTestId(`surface-diagnosis-palette-${kind}`).boundingBox();
    expect(box!.x).toBeGreaterThanOrEqual(0); expect(box!.x + box!.width).toBeLessThanOrEqual(390);
  }
  await page.screenshot({ path: testInfo.outputPath("surface-palette-mobile.png") });
  await page.getByTestId("clinical-surface-UL3-I").click({ button: "right" });
  const box = await menu.boundingBox();
  expect(box!.x).toBeGreaterThanOrEqual(0); expect(box!.x + box!.width).toBeLessThanOrEqual(390);
  await page.screenshot({ path: testInfo.outputPath("surface-menu-mobile.png") });
  const cancel = menu.getByTestId("clinical-surface-cancel");
  await cancel.scrollIntoViewIfNeeded();
  await expect(cancel).toBeVisible();
  await expect(cancel).toBeEnabled();
  const cancelBox = await cancel.boundingBox();
  const scrolledMenuBox = await menu.boundingBox();
  expect(cancelBox).not.toBeNull(); expect(scrolledMenuBox).not.toBeNull();
  expect(cancelBox!.x).toBeGreaterThanOrEqual(Math.max(0, scrolledMenuBox!.x));
  expect(cancelBox!.y).toBeGreaterThanOrEqual(Math.max(0, scrolledMenuBox!.y));
  expect(cancelBox!.x + cancelBox!.width).toBeLessThanOrEqual(Math.min(390, scrolledMenuBox!.x + scrolledMenuBox!.width));
  expect(cancelBox!.y + cancelBox!.height).toBeLessThanOrEqual(Math.min(844, scrolledMenuBox!.y + scrolledMenuBox!.height));
});
