import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { createElement, type ComponentProps } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { JsxEmit, ModuleKind, ScriptTarget, transpileModule } from "typescript";
import { planningApplianceConnections, projectCompletedPlanningTooth, projectCurrentCompletedTooth, type CompletedPlanningEffect } from "../components/clinical/planningAppearance";
import { planningApplianceError, planningItemTargetLabel, planningTargetTeeth, type PlanningAppliance, type PlanningItem, type PlanningNativeRow } from "../components/clinical/treatmentPlanning";
import { getToothAnatomy } from "../components/clinical/toothAnatomy";
import { surfaceMaterials } from "../components/clinical/surfaceDiagnosis";

const source = (): PlanningNativeRow => ({ revision: 7, condition: "present", movement: "forward",
  root_observations: { "1": { condition: "filled_defective", apicectomy: true } },
  crown_observation: { kind: "gold", issues: ["defective"] },
  surface_observations: { M: { kind: "carious", material: null, condition: "carious_early", defects: [] },
    D: { kind: "restored", material: "amalgam", condition: "sound", defects: [] } } });
const item = (id: number, kind: PlanningItem["drawing_kind"], patch: Partial<PlanningItem> = {}): PlanningItem => ({
  id, patient_id: 901, plan_id: 4, treatment_id: null, revision: 2, tooth: "UR6", surface: null,
  procedure_code: "SYNTHETIC", description: "Synthetic test treatment", fee_pence: 100,
  created_at: "2026-01-01T12:00:00Z", updated_at: "2026-02-01T12:00:00Z", status: "completed",
  target: { level: ["extraction", "implant"].includes(kind) ? "tooth" : ["root_canal", "post_core", "apicectomy"].includes(kind) ? "root" : ["filling", "sealant"].includes(kind) ? "surface" : "crown", tooth: "UR6", surfaces: kind === "filling" || kind === "sealant" ? ["M", "O", "D"] : [] },
  drawing_kind: kind, material: null, catalogue_snapshot: { source: "custom" }, fee_mode: "agreed", fee_reason: null,
  completed_procedure_id: id * 10, ...patch,
});
const effect = (entry: PlanningItem, eventId = entry.completed_procedure_id!): CompletedPlanningEffect => ({
  item_id: entry.id, procedure_id: entry.completed_procedure_id!, completed_at: "2026-02-01T12:00:00Z",
  event_id: eventId, target: entry.target, drawing_kind: entry.drawing_kind, material: entry.material, appliance: entry.appliance,
});

const appliance: PlanningAppliance = { kind: "bridge", arch: "upper", members: [
  { tooth: "UL6", role: "abutment" }, { tooth: "UL7", role: "pontic" }, { tooth: "UL8", role: "wing" },
] };
const group = (patch: Partial<PlanningItem> = {}) => item(41, "bridge", { target: { level: "crown", tooth: null, surfaces: [] },
  appliance, material: "porcelain_bonded", ...patch });

test("one appliance projects only explicit members, keeps support roots and never invents a native bridge identity", () => {
  const entry = group();
  const originals = { UL6: source(), UL7: { revision: 9, condition: "missing" as const }, UL8: source() };
  const frozen = JSON.stringify({ originals, entry });
  const appearances = Object.fromEntries(Object.entries(originals).map(([tooth, base]) =>
    [tooth, projectCompletedPlanningTooth(tooth, 901, base, undefined, [entry])]));
  for (const member of appliance.members) {
    expect(appearances[member.tooth].completionIds).toEqual([410]);
    expect(appearances[member.tooth].applianceItemId).toBe(41);
    expect(appearances[member.tooth].row.bridge_role).toBe(member.role);
    expect(appearances[member.tooth].row.bridge_group_id ?? null).toBeNull();
  }
  expect(appearances.UL6.row.root_observations).toEqual(originals.UL6.root_observations);
  expect(appearances.UL8.row.crown_observation).toEqual(originals.UL8.crown_observation);
  expect(appearances.UL7.row.condition).toBe("missing");
  expect(appearances.UL7.row.root_observations).toEqual({});
  expect(appearances.UL7.row.crown_observation?.kind).toBe("porcelain_bonded");
  expect(planningApplianceConnections([entry], appearances)).toEqual([expect.objectContaining({ id: "planning-41", planningStatus: "completed", span_start: "UL6", span_end: "UL8" })]);
  expect(projectCompletedPlanningTooth("UR6", 901, source(), undefined, [entry]).completionIds).toEqual([]);
  expect(projectCompletedPlanningTooth("UL7", 902, originals.UL7, undefined, [entry]).completionIds).toEqual([]);
  expect(projectCompletedPlanningTooth("UL7", 901, originals.UL7, undefined, [{ ...entry, status: "accepted", completed_procedure_id: null }]).row.crown_observation).toBeNull();
  expect(JSON.stringify({ originals, entry })).toBe(frozen);
});

test("noncontiguous denture members share one completion without filling gaps or changing underlying absence", () => {
  const entry = group({ drawing_kind: "denture", material: "denture_acrylic", appliance: { kind: "denture", arch: "lower", members: [
    { tooth: "LR1", role: "denture" }, { tooth: "LL6", role: "denture" },
  ] } });
  expect(planningTargetTeeth(entry)).toEqual(["LR1", "LL6"]);
  for (const tooth of ["LR1", "LL6"]) {
    const view = projectCurrentCompletedTooth(tooth, 901, { revision: 7, condition: "missing" }, undefined, [effect(entry)]);
    expect(view.row.condition).toBe("missing");
    expect(view.row.crown_observation?.kind).toBe("denture_acrylic");
    expect(view.row.root_observations).toEqual({});
    expect(view.completionIds).toEqual([410]);
  }
  expect(projectCurrentCompletedTooth("LL1", 901, source(), undefined, [effect(entry)]).completionIds).toEqual([]);
});

test("later member materials remain authoritative without erasing appliance identity, while explicit identity/reset masks connectors", () => {
  const entry = group();
  const raw = { ...source(), crown_observation: { kind: "composite" as const, issues: [] } };
  const views = Object.fromEntries(appliance.members.map(({ tooth }) => [tooth, projectCurrentCompletedTooth(tooth, 901,
    tooth === "UL7" ? { revision: 5, condition: "missing" } : raw, undefined, [effect(entry, 50)], tooth === "UL6" ? { crown: 60 } : {})]));
  expect(views.UL6.row.crown_observation).toEqual(raw.crown_observation);
  expect(views.UL6.applianceItemId).toBe(41);
  expect(views.UL7.applianceItemId).toBe(41);
  expect(planningApplianceConnections([entry], views)).toHaveLength(1);
  const changedPontic = projectCurrentCompletedTooth("UL7", 901, { revision: 8, condition: "missing", crown_observation: raw.crown_observation }, undefined, [effect(entry, 50)], { crown: 60 });
  expect(changedPontic.row.bridge_role).toBe("pontic");
  expect(changedPontic.row.crown_observation).toEqual(raw.crown_observation);
  const nativeIdentity = projectCurrentCompletedTooth("UL6", 901, raw, undefined, [effect(entry, 50)], { appliance: 70 });
  expect(nativeIdentity.applianceItemId).toBeNull();
  expect(planningApplianceConnections([entry], { ...views, UL6: nativeIdentity })).toEqual([]);
  expect(projectCurrentCompletedTooth("UL6", 901, raw, undefined, [], { crown: 60 }).row.crown_observation).toEqual(raw.crown_observation);
  expect(projectCurrentCompletedTooth("UL7", 901, { revision: 6, condition: "unrecorded" }, undefined, [effect(entry, 50)], { anatomy: 70 }).completionIds).toEqual([]);
});

test("appliance validation and labels use explicit role and arch, while pending connectors are planning-only", () => {
  expect(planningApplianceError(appliance)).toBeNull();
  expect(planningApplianceError({ ...appliance, members: [appliance.members[0], appliance.members[2]] })).toContain("neighbouring");
  expect(planningApplianceError({ ...appliance, members: [{ tooth: "UL6", role: "abutment" }, { tooth: "LL7", role: "pontic" }] })).toContain("one arch");
  expect(planningItemTargetLabel(group())).toContain("UL7 (pontic)");
  const proposed = group({ status: "proposed", completed_procedure_id: null });
  expect(planningApplianceConnections([proposed], {})).toEqual([expect.objectContaining({ id: "planning-41", planningStatus: "planned" })]);
  expect(planningApplianceConnections([proposed], {}, false)).toEqual([]);
});

test("reviewed native support evidence overrides stale dentures, but impacted and unresolved implant wings cannot project", () => {
  const entry = group();
  const legacy = { restorations: [{ type: "denture" as const }] };
  expect(projectCompletedPlanningTooth("UL6", 901, { revision: 0 }, legacy, [entry]).applianceItemId).toBeNull();
  expect(projectCompletedPlanningTooth("UL6", 901, { revision: 2, condition: "unrecorded" }, legacy, [entry]).applianceItemId).toBe(41);
  expect(projectCompletedPlanningTooth("UL6", 901, { revision: 2, root_observations: { "1": { condition: null, apicectomy: false } } }, legacy, [entry]).applianceItemId).toBe(41);
  expect(projectCompletedPlanningTooth("UL6", 901, { revision: 2, condition: "impacted" }, undefined, [entry]).applianceItemId).toBeNull();
  expect(projectCompletedPlanningTooth("UL8", 901, { revision: 0 }, { restorations: [{ type: "implant" }] }, [entry]).applianceItemId).toBeNull();
  expect(projectCompletedPlanningTooth("UL6", 901, { revision: 2, condition: "implant" }, undefined, [entry]).applianceItemId).toBe(41);
});

test("completed appearance folds actual completion order and Uncomplete restores the preceding appearance without changing source", () => {
  const original = source();
  const legacy = { missing: false, extracted: false, restorations: [{ type: "crown" as const }] };
  const before = JSON.stringify({ original, legacy });
  const crown = item(1, "crown", { material: "porcelain_bonded", updated_at: "2027-01-01T00:00:00Z" });
  const extraction = item(2, "extraction");
  const completed = projectCompletedPlanningTooth("UR6", 901, original, legacy, [extraction, crown]);
  expect(completed.row.condition).toBe("missing");
  expect(completed.row.root_observations).toEqual({});
  expect(completed.row.crown_observation).toBeNull();
  expect(completed.row.surface_observations).toEqual({});
  expect(completed.completionIds).toEqual([10, 20]);
  expect(completed.legacy.restorations).toEqual([]);
  const undone = projectCompletedPlanningTooth("UR6", 901, original, legacy, [crown, { ...extraction, status: "accepted", completed_procedure_id: null }]);
  expect(undone.row.condition).toBe("present");
  expect(undone.row.crown_observation).toEqual({ kind: "porcelain_bonded", issues: [] });
  expect(undone.row.revision).toBe(7);
  const allUndone = projectCompletedPlanningTooth("UR6", 901, original, legacy, []);
  expect(allUndone.row).toEqual(original);
  expect(JSON.stringify({ original, legacy })).toBe(before);
});

test("only active same-patient same-tooth completions project and no natural root is invented at absent sites", () => {
  const missing: PlanningNativeRow = { revision: 8, condition: "missing" };
  const ignored = [item(1, "implant", { patient_id: 902 }), item(2, "implant", { target: { level: "tooth", tooth: "LL6", surfaces: [] } }),
    ...(["proposed", "accepted", "declined", "cancelled"] as const).map((status, i) => item(3 + i, "implant", { status })), item(10, "implant", { completed_procedure_id: null })];
  expect(projectCompletedPlanningTooth("UR6", 901, missing, undefined, ignored).row.condition).toBe("missing");
  const unsafe = projectCompletedPlanningTooth("UR6", 901, missing, undefined, [item(11, "crown", { material: "gold" }), item(12, "root_canal")]);
  expect(unsafe.row.condition).toBe("missing");
  expect(unsafe.row.root_observations).toEqual({});
  expect(unsafe.unappliedCompletionIds).toEqual([110, 120]);
  const restored = projectCompletedPlanningTooth("UR6", 901, missing, undefined, [item(1, "implant"), item(2, "crown", { material: "porcelain_bonded" })]);
  expect(restored.row.condition).toBe("implant");
  expect(restored.row.root_observations).toEqual({});
  expect(restored.row.crown_observation?.kind).toBe("porcelain_bonded");
});

test("completed root work uses whole natural root area and surface work changes only its canonical surfaces", () => {
  for (const quadrant of ["UR", "UL", "LR", "LL"]) {
    const tooth = `${quadrant}4`;
    const base = { ...source(), dentition: "deciduous" as const };
    const target = { level: "root" as const, tooth, surfaces: [] };
    const result = projectCompletedPlanningTooth(tooth, 901, base, undefined, [item(1, "root_canal", { target }), item(2, "post_core", { target }), item(3, "apicectomy", { target })]);
    expect(Object.keys(result.row.root_observations!)).toHaveLength(getToothAnatomy(tooth, "deciduous").roots.length);
    expect(Object.values(result.row.root_observations!).every((entry) => entry.condition === "post_core_sound" && entry.apicectomy)).toBeTruthy();
    const surface = quadrant.startsWith("U") ? "P" : "L";
    const filled = projectCompletedPlanningTooth(tooth, 901, base, undefined, [item(4, "filling", { material: "resin", target: { level: "surface", tooth, surfaces: ["M", surface] } })]);
    expect(filled.row.surface_observations?.M).toEqual({ kind: "restored", material: "resin", condition: "sound", defects: [] });
    expect(filled.row.surface_observations?.[surface]?.material).toBe("resin");
    expect(filled.row.surface_observations?.D).toEqual(base.surface_observations?.D);
  }
});

test("unspecified material is neutral and explicit denture remains rootless without inventing biological presence", () => {
  const neutral = projectCompletedPlanningTooth("UR6", 901, source(), undefined, [item(1, "crown"), item(2, "filling")]);
  expect(neutral.row.crown_observation).toEqual({ kind: null, issues: [] });
  expect(neutral.row.surface_observations?.M?.material).toBeNull();
  const denture = projectCompletedPlanningTooth("UR6", 901, { revision: 3, condition: "missing" }, undefined,
    [item(1, "denture", { material: "denture_cocr" })]);
  expect(denture.row.condition).toBe("missing");
  expect(denture.row.crown_observation?.kind).toBe("denture_cocr");
  expect(denture.row.root_observations).toEqual({});
});

test("Current precedence preserves later movement and dentition while extraction still overrides old anatomy", () => {
  const base = { ...source(), dentition: "deciduous" as const, rotation: "clockwise" as const };
  const extraction = effect(item(1, "extraction"), 20);
  const events = { movement: 25, dentition: 26, rotation: 27 };
  const result = projectCurrentCompletedTooth("UR6", 901, base, { missing: false, restorations: [{ type: "crown" }] }, [extraction], events);
  expect(result.row.condition).toBe("missing");
  expect(result.row.movement).toBe("forward");
  expect(result.row.rotation).toBe("clockwise");
  expect(result.row.dentition).toBe("deciduous");
  expect(result.legacy.restorations).toEqual([]);
  expect(projectCurrentCompletedTooth("UR6", 901, base, undefined, [extraction], { ...events, anatomy: 30 }).row).toEqual(base);
});

test("Current per-field audit masks preserve later crown/root/apicectomy and individual surface observations", () => {
  const base = source();
  const effects = [effect(item(1, "crown", { material: "porcelain" }), 10), effect(item(2, "filling", { material: "resin" }), 20),
    effect(item(3, "root_canal"), 30), effect(item(4, "apicectomy"), 40)];
  const result = projectCurrentCompletedTooth("UR6", 901, base, undefined, effects,
    { crown: 15, surfaces: { M: 25 }, root_condition: 35, apicectomy: 45 });
  expect(result.row.crown_observation).toEqual(base.crown_observation);
  expect(result.row.surface_observations?.M).toEqual(base.surface_observations?.M);
  expect(result.row.surface_observations?.O?.material).toBe("resin");
  expect(result.row.surface_observations?.D?.material).toBe("resin");
  expect(result.row.root_observations).toEqual(base.root_observations);
  expect(result.unappliedCompletionIds).toEqual([]);
});

const componentFile = resolve(__dirname, "../components/clinical/OdontogramToothSvg.tsx");
const componentModule = { exports: {} as typeof import("../components/clinical/OdontogramToothSvg") };
new Function("require", "module", "exports", transpileModule(readFileSync(componentFile, "utf8"), {
  compilerOptions: { module: ModuleKind.CommonJS, jsx: JsxEmit.ReactJSX, target: ScriptTarget.ES2017 },
}).outputText)(createRequire(componentFile), componentModule, componentModule.exports);
const { default: Tooth, getOdontogramToothType } = componentModule.exports;
type Props = ComponentProps<typeof Tooth>;
let serial = 0;
function markup(tooth: string, props: Partial<Props>) {
  return renderToStaticMarkup(createElement(Tooth, { toothKey: tooth, toothType: getOdontogramToothType(tooth), ...props }), { identifierPrefix: `effects-${serial++}-` });
}
const css = "body{margin:24px;font:14px system-ui}.tooth{width:90px;padding-top:55px}.odontogram-tooth-svg{width:100%;height:auto;overflow:visible}.clinical-root-halo,.clinical-crown-halo,.clinical-surface-halo{opacity:0}";
test("completed extraction and implant glyphs replace anatomy, preserve slots and notes, and retain C without duplicate artwork", async ({ page }) => {
  for (const quadrant of ["UR", "UL", "LR", "LL"]) {
    const tooth = `${quadrant}6`;
    for (const kind of ["extraction", "implant"] as const) {
      const entry = item(1, kind, { target: { level: "tooth", tooth, surfaces: [] } });
      const result = projectCompletedPlanningTooth(tooth, 901, source(), undefined, [entry]);
      await page.setContent(`<style>${css}</style><div class="tooth">${markup(tooth, {
        baselineCondition: { status: result.row.condition as "missing" | "implant" }, rootConditions: result.row.root_observations,
        crownCondition: result.row.crown_observation, surfaceObservations: result.row.surface_observations, hasToothNote: true,
        plannedOverlays: [{ id: 1, kind, label: "Synthetic completed work", status: "completed", badgeOnly: true }],
      })}</div>`);
      await expect(page.getByTestId(`tooth-svg-${tooth}`)).toHaveAttribute("viewBox", "0 0 100 280");
      await expect(page.getByTestId(`tooth-note-flag-${tooth}`)).toBeAttached();
      await expect(page.getByTestId(`tooth-planning-count-${tooth}-completed`)).toContainText("C");
      await expect(page.getByTestId(`tooth-planning-overlay-${tooth}-1`).locator("path,polygon")).toHaveCount(0);
      await expect(page.locator(`[data-testid^="tooth-root-${tooth}-"]`)).toHaveCount(0);
      await expect(page.getByTestId(`tooth-baseline-implant-${tooth}`)).toHaveCount(kind === "implant" ? 1 : 0);
      await expect(page.getByTestId(`tooth-anatomy-${tooth}`)).toHaveCount(kind === "implant" ? 1 : 0);
    }
  }
});

test("planned material fills reuse diagnosis colours and extraction cross is blue-green in a light/dark gallery", async ({ page }, testInfo) => {
  const crown = markup("UR6", { crownCondition: { kind: "porcelain_bonded", issues: [] }, rootConditions: {}, surfaceObservations: {} });
  const pending = markup("UL6", { rootConditions: {}, surfaceObservations: {}, plannedOverlays: [
    { id: 1, kind: "crown", label: "Bonded crown", material: "porcelain_bonded", status: "planned" },
    { id: 2, kind: "filling", label: "Composite", material: "resin", surfaces: ["M", "O", "D"], status: "planned" },
  ] });
  const extraction = markup("LL6", { rootConditions: {}, surfaceObservations: {}, plannedOverlays: [{ id: 3, kind: "extraction", label: "Extraction", status: "planned" }] });
  for (const theme of ["light", "dark"]) {
    await page.setContent(`<style>${css}body{background:${theme === "dark" ? "#171614" : "#faf8f4"};color:${theme === "dark" ? "#faf8f4" : "#282624"};--planning-ink:${theme === "dark" ? "#55d4ee" : "#006f88"};--planning-extraction:${theme === "dark" ? "#55dcc2" : "#008d91"};--planning-halo:${theme === "dark" ? "#27212f" : "#faf8ff"}}main{display:flex;gap:30px}</style><main><div><p>Diagnosis bonded crown</p><div class="tooth">${crown}</div></div><div><p>Planned material</p><div class="tooth">${pending}</div></div><div><p>Planned extraction</p><div class="tooth">${extraction}</div></div></main>`);
    await expect(page.getByTestId("tooth-planning-crown-UL6-1")).toHaveAttribute("fill", await page.getByTestId("tooth-crown-UR6").getAttribute("fill") as string);
    await expect(page.getByTestId("tooth-planning-surface-UL6-2-M").locator("polygon").last()).toHaveAttribute("fill", surfaceMaterials.find((material) => material.value === "resin")!.colour);
    const stroke = await page.getByTestId("tooth-planning-extraction-LL6-3").evaluate((element) => getComputedStyle(element).stroke);
    expect(stroke).toBe(theme === "dark" ? "rgb(85, 220, 194)" : "rgb(0, 141, 145)");
    await page.screenshot({ path: testInfo.outputPath(`completed-material-${theme}.png`), fullPage: true });
  }
});

test("grouped appliance glyphs show explicit roles, rootless completed replacements and non-destructive pending artwork", async ({ page }, testInfo) => {
  for (const upper of [true, false]) {
    const teeth = [6, 7, 8].map((position) => `${upper ? "UL" : "LL"}${position}`);
    const entry = group({ appliance: { ...appliance, arch: upper ? "upper" : "lower", members: appliance.members.map((member, index) => ({ ...member, tooth: teeth[index] })) } });
    const groupMarkup = (completed: boolean) => teeth.map((tooth, index) => {
      const base: PlanningNativeRow = index === 1 ? { revision: 1, condition: "missing" } : source();
      const view = projectCompletedPlanningTooth(tooth, 901, base, undefined, completed ? [entry] : []);
      return `<div class="tooth">${markup(tooth, {
        baselineCondition: { status: view.row.condition as "present" | "missing" },
        rootConditions: view.row.root_observations, crownCondition: view.row.crown_observation,
        surfaceObservations: view.row.surface_observations, bridgeRole: view.row.bridge_role,
        plannedOverlays: [{ id: 41, kind: "bridge", material: "porcelain_bonded", applianceRole: entry.appliance!.members[index].role,
          label: "One synthetic appliance", status: completed ? "completed" : "planned", badgeOnly: completed }],
      })}</div>`;
    }).join("");
    for (const theme of ["light", "dark"]) {
      await page.setContent(`<style>${css}body{background:${theme === "dark" ? "#171614" : "#faf8f4"};color:${theme === "dark" ? "#faf8f4" : "#282624"}}section{display:flex;gap:20px}.clinical-crown-selection{opacity:0}</style><h2>Planned: one appliance</h2><section id="pending">${groupMarkup(false)}</section><h2>Completed: same appliance</h2><section id="completed">${groupMarkup(true)}</section>`);
      const pending = page.locator("#pending"), completed = page.locator("#completed");
      await expect(pending.getByTestId(`tooth-planning-overlay-${teeth[1]}-41`)).toHaveAttribute("data-appliance-role", "pontic");
      await expect(completed.locator(`[data-testid^="tooth-root-${teeth[1]}-"]`)).toHaveCount(0);
      expect(await completed.locator(`[data-testid^="tooth-root-${teeth[0]}-"]`).count()).toBeGreaterThan(0);
      await expect(completed.getByTestId(`clinical-bridge-wing-${teeth[2]}`)).toBeAttached();
      await expect(completed.getByTestId(`tooth-crown-${teeth[1]}`)).toHaveAttribute("fill", "#70483b");
      await expect(pending.getByTestId(`tooth-planning-wing-${teeth[2]}-41`)).toBeAttached();
      await expect(completed.getByTestId(`tooth-planning-overlay-${teeth[1]}-41`).locator("path")).toHaveCount(0);
      await page.screenshot({ path: testInfo.outputPath(`appliance-${upper ? "upper" : "lower"}-${theme}.png`), fullPage: true });
    }
  }
});
