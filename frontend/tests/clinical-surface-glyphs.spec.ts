import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { createElement, type ComponentProps } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { JsxEmit, ModuleKind, ScriptTarget, transpileModule } from "typescript";
import { surfaceMaterials, surfaceKeysForTooth, surfaceName, newSurfaceObservation, surfaceSelectionLabel, toggleSurfaceTarget, type SurfaceObservation, type SurfaceKey } from "../components/clinical/surfaceDiagnosis";

// Render the actual component in a blank browser, without a server or patients.
const componentFile = resolve(__dirname, "../components/clinical/OdontogramToothSvg.tsx");
const componentModule = { exports: {} as typeof import("../components/clinical/OdontogramToothSvg") };
new Function("require", "module", "exports", transpileModule(readFileSync(componentFile, "utf8"), {
  compilerOptions: { module: ModuleKind.CommonJS, jsx: JsxEmit.ReactJSX, target: ScriptTarget.ES2017 },
}).outputText)(createRequire(componentFile), componentModule, componentModule.exports);
const { default: Tooth, getOdontogramToothType } = componentModule.exports;
type ToothProps = ComponentProps<typeof Tooth>;
const quadrants = ["UR", "UL", "LR", "LL"] as const;
const noAction = () => {};
const restored: SurfaceObservation = { kind: "restored", material: "amalgam", condition: "sound", defects: [] };
const neutral = newSurfaceObservation(null);
let sequence = 0;
function markup(toothKey: string, props: Partial<ToothProps> = {}) {
  return renderToStaticMarkup(createElement(Tooth, { toothKey, toothType: getOdontogramToothType(toothKey), ...props }), { identifierPrefix: `surface-${sequence++}-` });
}
function currentProps(): Partial<ToothProps> {
  return { surfaceObservations: {}, onDiagnosticSurfaceClick: noAction, onDiagnosticSurfaceContextMenu: noAction };
}
async function render(page: Page, tooth: string, props: Partial<ToothProps> = {}) {
  await page.setContent(`<style>body{margin:30px}svg{width:100px;height:280px}.clinical-root-halo,.clinical-crown-halo,.clinical-surface-halo{opacity:0}</style>${markup(tooth, props)}`);
  return page.getByTestId(`tooth-svg-${tooth}`);
}

test("surface catalogue defaults preserve unspecified stages and canonical tooth surface keys", () => {
  expect(newSurfaceObservation("carious")).toEqual({ kind: "carious", material: null, condition: null, defects: [] });
  expect(newSurfaceObservation("restored")).toEqual({ kind: "restored", material: "unknown", condition: null, defects: [] });
  expect(newSurfaceObservation("sealant")).toEqual({ kind: "sealant", material: null, condition: null, defects: [] });
  expect(newSurfaceObservation("defective")).toEqual({ kind: "defective", material: null, condition: "defective", defects: [] });
  expect(newSurfaceObservation(null)).toEqual({ kind: null, material: null, condition: null, defects: [] });
  for (const quadrant of quadrants) {
    for (let position = 1; position <= 8; position += 1) {
      expect(surfaceKeysForTooth(`${quadrant}${position}`)).toEqual([
        "M", position <= 3 ? "I" : "O", "D", "B", quadrant.startsWith("U") ? "P" : "L",
      ]);
    }
  }
});

test("surface selection includes right-click targets without losing other teeth and toggles in canonical order", () => {
  let targets = toggleSurfaceTarget([], "UR6", "D");
  targets = toggleSurfaceTarget(targets, "UR6", "M");
  targets = toggleSurfaceTarget(targets, "LL3", "I");
  const before = JSON.stringify(targets);
  const included = toggleSurfaceTarget(targets, "UR6", "M", true);
  expect(included).toEqual(expect.arrayContaining([
    { tooth: "UR6", surfaces: ["M", "D"] }, { tooth: "LL3", surfaces: ["I"] },
  ]));
  expect(JSON.stringify(targets)).toBe(before);
  targets = toggleSurfaceTarget(included, "UR6", "O", true);
  expect(surfaceSelectionLabel(targets)).toBe("LL3 I · UR6 MOD");
  targets = toggleSurfaceTarget(targets, "UR6", "M");
  expect(surfaceSelectionLabel(targets)).toBe("LL3 I · UR6 OD");
  targets = toggleSurfaceTarget(targets, "LL3", "I");
  expect(targets).toEqual([{ tooth: "UR6", surfaces: ["O", "D"] }]);
  expect(surfaceSelectionLabel([{ tooth: "UL6", surfaces: ["P", "D", "M", "B", "O"] }])).toBe("UL6 MODBP");
});

test("Current surface availability and mesial orientation are correct without remapping History", async ({ page }) => {
  for (const quadrant of quadrants) {
    for (const position of [1, 3, 4, 6]) {
      const tooth = `${quadrant}${position}`;
      await render(page, tooth);
      const historicalM = await page.getByTestId(`tooth-surface-${tooth}-M`).boundingBox();
      const historicalD = await page.getByTestId(`tooth-surface-${tooth}-D`).boundingBox();
      const crown = await page.getByTestId(`tooth-crown-${tooth}`).getAttribute("d");
      expect(historicalM!.x).toBeLessThan(historicalD!.x);
      await render(page, tooth, currentProps());
      const m = await page.getByTestId(`clinical-surface-${tooth}-M`).boundingBox();
      const d = await page.getByTestId(`clinical-surface-${tooth}-D`).boundingBox();
      expect(m!.x > d!.x).toBe(quadrant.endsWith("R"));
      await expect(page.getByTestId(`tooth-crown-${tooth}`)).toHaveAttribute("d", crown!);
      for (const surface of surfaceKeysForTooth(tooth)) {
        const target = page.getByTestId(`clinical-surface-${tooth}-${surface}`);
        await expect(target).toHaveAttribute("role", "button");
        await expect(target).toHaveAttribute("tabindex", "0");
        await expect(target).toHaveAttribute("aria-label", `${tooth} ${surfaceName(surface)} surface`);
        await expect(target).toHaveAttribute("aria-pressed", "false");
      }
      await expect(page.locator('.clinical-surface-target')).toHaveCount(5);
      await expect(page.getByTestId(`clinical-surface-${tooth}-${position <= 3 ? "O" : "I"}`)).toHaveCount(0);
      await expect(page.getByTestId(`clinical-surface-${tooth}-${quadrant.startsWith("U") ? "L" : "P"}`)).toHaveCount(0);
      const buccal = (await page.getByTestId(`clinical-surface-${tooth}-B`).boundingBox())!;
      const inner = (await page.getByTestId(`clinical-surface-${tooth}-${quadrant.startsWith("U") ? "P" : "L"}`).boundingBox())!;
      expect(buccal.y).toBeLessThan(inner.y); // Existing vertical convention is deliberately retained.
      await render(page, tooth);
      expect(await page.getByTestId(`tooth-surface-${tooth}-M`).boundingBox()).toEqual(historicalM);
      await expect(page.locator('.clinical-surface-target')).toHaveCount(0);
    }
    const primary = `${quadrant}4`;
    await render(page, primary, { ...currentProps(), baselineCondition: { dentition: "deciduous" } });
    await expect(page.getByTestId(`clinical-surface-${primary}-O`)).toHaveAttribute("aria-label", `${quadrant}D Occlusal surface`);
  }
});

test("all catalogue materials fill only the chosen surface and announce their actual material", async ({ page }) => {
  for (const quadrant of quadrants) {
    const tooth = `${quadrant}6`;
    for (const material of surfaceMaterials) {
      await render(page, tooth, { ...currentProps(), surfaceObservations: { M: { ...restored, material: material.value } } });
      const fill = page.getByTestId(`clinical-surface-fill-${tooth}-M`);
      await expect(fill).toHaveAttribute("fill", material.colour);
      await expect(fill).toHaveAttribute("points", (await page.getByTestId(`tooth-surface-${tooth}-M`).getAttribute("points"))!);
      await expect(page.getByTestId(`clinical-surface-${tooth}-M`).locator("title")).toContainText(material.label);
      await expect(page.getByTestId(`clinical-surface-${tooth}-M`)).toHaveAttribute("data-surface-condition", "sound");
      await expect(page.getByTestId(`clinical-surface-finding-${tooth}-D`)).toHaveCount(0);
      await expect(page.locator('[data-testid^="clinical-surface-pattern-"]')).toHaveCount(0);
    }
  }
});

test("caries stages and defects use distinct contained patterns and never label unspecified as sound", async ({ page }) => {
  for (const quadrant of quadrants) {
    const tooth = `${quadrant}6`;
    const patterns = new Set<string>();
    for (const stage of ["early", "arrested", "established", "unspecified"] as const) {
      await render(page, tooth, { ...currentProps(), surfaceObservations: { O: {
        kind: "carious", material: null, condition: stage === "unspecified" ? null : `carious_${stage}`, defects: [],
      } } });
      const marker = page.getByTestId(`clinical-surface-pattern-${tooth}-O`);
      await expect(marker).toHaveAttribute("data-stage", stage);
      await expect(marker).toHaveAttribute("points", (await page.getByTestId(`tooth-surface-${tooth}-O`).getAttribute("points"))!);
      patterns.add(await marker.evaluate((element) => document.getElementById(element.getAttribute("fill")!.slice(5, -1))!.innerHTML));
      if (stage === "unspecified") {
        await expect(page.getByTestId(`clinical-surface-${tooth}-O`).locator("title")).toContainText("Stage unspecified");
        await expect(page.getByTestId(`clinical-surface-${tooth}-O`).locator("title")).not.toContainText("Sound");
      }
    }
    expect(patterns.size).toBe(4);
    for (const kind of ["defective", "restored", "sealant"] as const) {
      await render(page, tooth, { ...currentProps(), surfaceObservations: { O: {
        kind, material: kind === "restored" ? "gold" : null, condition: "defective", defects: ["cracked", "leaking"],
      } } });
      await expect(page.getByTestId(`clinical-surface-pattern-${tooth}-O`)).toHaveAttribute("data-pattern", "defective");
      await expect(page.getByTestId(`clinical-surface-${tooth}-O`).locator("title")).toContainText("Cracked");
      await expect(page.getByTestId(`clinical-surface-${tooth}-O`).locator("title")).toContainText("Leaking");
    }
  }
});

test("multi-selection and halo paths preserve the surface, tooth, crown and root geometry", async ({ page }) => {
  for (const quadrant of quadrants) {
    const tooth = `${quadrant}6`;
    const props: Partial<ToothProps> = { ...currentProps(), rootConditions: { "1": { condition: "post_core_sound", apicectomy: true } },
      crownCondition: { kind: "porcelain_bonded", issues: [] }, bridgeRole: "wing" };
    await render(page, tooth, props);
    const before = await page.getByTestId(`tooth-svg-${tooth}`).boundingBox();
    const crown = await page.getByTestId(`tooth-crown-${tooth}`).getAttribute("d");
    const root = await page.getByTestId(`tooth-root-${tooth}-1`).getAttribute("d");
    const map = await page.getByTestId(`tooth-surface-map-${tooth}`).boundingBox();
    const selected: SurfaceKey[] = ["M", "O", "D"];
    await render(page, tooth, { ...props, selectedDiagnosticSurfaces: selected, surfaceObservations: { M: restored, O: restored, D: restored } });
    for (const surface of surfaceKeysForTooth(tooth)) {
      const target = page.getByTestId(`clinical-surface-${tooth}-${surface}`);
      await expect(target).toHaveAttribute("aria-pressed", String(selected.includes(surface)));
      await expect(target.locator('.clinical-surface-halo')).toHaveAttribute("points", (await target.locator('polygon').first().getAttribute("points"))!);
    }
    await expect(page.locator('.clinical-surface-selection')).toHaveCount(3);
    expect(await page.getByTestId(`tooth-svg-${tooth}`).boundingBox()).toEqual(before);
    expect(await page.getByTestId(`tooth-surface-map-${tooth}`).boundingBox()).toEqual(map);
    await expect(page.getByTestId(`tooth-crown-${tooth}`)).toHaveAttribute("d", crown!);
    await expect(page.getByTestId(`tooth-root-${tooth}-1`)).toHaveAttribute("d", root!);
    await expect(page.getByTestId(`clinical-root-finding-${tooth}-1`)).toBeAttached();
    await expect(page.getByTestId(`clinical-root-apicectomy-${tooth}-1`)).toBeAttached();
    await expect(page.getByTestId(`clinical-bridge-wing-${tooth}`)).toBeAttached();
  }
});

test("per-surface reset suppresses conflicting legacy marks only on that surface and leaves History intact", async ({ page }) => {
  for (const quadrant of quadrants) {
    const tooth = `${quadrant}6`;
    const inner: SurfaceKey = quadrant.startsWith("U") ? "P" : "L";
    const restorations: ToothProps["restorations"] = [
      { type: "filling", surfaces: ["M", "D", "L"] }, { type: "filling" }, { type: "veneer", surfaces: ["B"] },
      { type: "inlay_onlay", surfaces: ["O"] }, { type: "root_canal" }, { type: "post" }, { type: "crown" },
    ];
    await render(page, tooth, { ...currentProps(), restorations, surfaceObservations: { M: neutral, B: neutral, [inner]: neutral } });
    for (const key of ["M", "L"]) await expect(page.getByTestId(`tooth-restoration-${tooth}-filling-${key}`)).toHaveCount(0);
    await expect(page.getByTestId(`tooth-restoration-${tooth}-filling-D`)).toBeAttached();
    await expect(page.getByTestId(`tooth-restoration-${tooth}-filling-generic`)).toHaveCount(0);
    await expect(page.getByTestId(`tooth-restoration-${tooth}-veneer-B`)).toHaveCount(0);
    await expect(page.getByTestId(`tooth-restoration-${tooth}-veneer`)).toHaveCount(0);
    await expect(page.getByTestId(`tooth-restoration-${tooth}-inlay_onlay-O`)).toBeAttached();
    await expect(page.getByTestId(`clinical-surface-${tooth}-M`)).toHaveAttribute("data-surface-kind", "unspecified");
    await expect(page.getByTestId(`clinical-surface-${tooth}-M`)).toHaveAttribute("data-surface-recorded", "true");
    await expect(page.getByTestId(`clinical-surface-fill-${tooth}-M`)).toHaveCount(0);
    for (const type of ["crown", "root_canal", "post"]) await expect(page.getByTestId(`tooth-anatomy-restoration-${tooth}-${type}`)).toBeAttached();
    await render(page, tooth, { restorations });
    for (const key of ["M", "D", "L"]) await expect(page.getByTestId(`tooth-restoration-${tooth}-filling-${key}`)).toBeAttached();
    await expect(page.getByTestId(`tooth-restoration-${tooth}-filling-generic`)).toBeAttached();
    await expect(page.getByTestId(`tooth-restoration-${tooth}-veneer-B`)).toBeAttached();
  }
});

test("incompatible anatomy and untouched legacy absence or implants expose no diagnostic surface controls", async ({ page }) => {
  for (const quadrant of quadrants) {
    const tooth = `${quadrant}6`;
    const incompatible: Partial<ToothProps>[] = [
      { baselineCondition: { status: "missing" } }, { baselineCondition: { status: "unerupted" } },
      { baselineCondition: { status: "implant" } }, { bridgeRole: "pontic" },
      { crownCondition: { kind: "denture_cocr", issues: [] } }, { crownCondition: { kind: "denture_acrylic", issues: [] } },
      { crownCondition: { kind: "fractured", issues: [] } }, { restorations: [{ type: "implant" }] },
    ];
    for (const props of incompatible) {
      await render(page, tooth, { ...currentProps(), ...props, surfaceObservations: { M: restored } });
      await expect(page.locator('.clinical-surface-target')).toHaveCount(0);
      await expect(page.getByTestId(`clinical-surface-finding-${tooth}-M`)).toHaveCount(0);
    }
    for (const props of [{ missing: true }, { extracted: true }]) {
      await render(page, tooth, { ...currentProps(), ...props });
      await expect(page.locator('.clinical-surface-target')).toHaveCount(0);
    }
    await render(page, tooth, { ...currentProps(), crownCondition: { kind: "missing", issues: [] } });
    await expect(page.locator('.clinical-surface-target')).toHaveCount(5);
    await expect(page.getByTestId(`clinical-crown-stump-${tooth}`)).toBeAttached();
  }
});

test("native surface evidence resolves stale absence without unlocking root authoring or overriding a legacy implant", async ({ page }) => {
  for (const quadrant of quadrants) {
    const tooth = `${quadrant}6`;
    const props: Partial<ToothProps> = { ...currentProps(), missing: true, extracted: true,
      onRootClick: noAction, rootConditions: {}, restorations: [{ type: "extraction" }], surfaceObservations: { M: restored } };
    await render(page, tooth, props);
    await expect(page.getByTestId(`clinical-surface-finding-${tooth}-M`)).toBeAttached();
    await expect(page.getByTestId(`tooth-restoration-${tooth}-missing`)).toHaveCount(0);
    await expect(page.getByTestId(`tooth-restoration-${tooth}-extraction`)).toHaveCount(0);
    await expect(page.getByTestId(`clinical-root-${tooth}`)).not.toHaveAttribute("role");
    await expect(page.getByTestId(`tooth-svg-${tooth}`)).not.toHaveAttribute("aria-label", /present|healthy/);
    await render(page, tooth, { ...props, restorations: [{ type: "implant" }] });
    await expect(page.getByTestId(`tooth-anatomy-restoration-${tooth}-implant`)).toBeAttached();
    await expect(page.getByTestId(`tooth-restoration-${tooth}-implant`)).toBeAttached();
    await expect(page.locator('.clinical-surface-target')).toHaveCount(0);
    await expect(page.getByTestId(`clinical-surface-finding-${tooth}-M`)).toHaveCount(0);
    await render(page, tooth, { ...props, baselineCondition: { status: "present" }, restorations: [{ type: "implant" }] });
    await expect(page.getByTestId(`clinical-surface-finding-${tooth}-M`)).toBeAttached();
    await expect(page.getByTestId(`tooth-anatomy-restoration-${tooth}-implant`)).toHaveCount(0);
  }
});

test("synthetic surface gallery shows multi-surface materials and differentiated findings in both themes", async ({ page }, testInfo) => {
  const examples: Array<{ label: string; tooth: string; map: Partial<Record<SurfaceKey, SurfaceObservation>> }> = [
    { label: "MOD amalgam", tooth: "UR6", map: { M: restored, O: restored, D: restored } },
    { label: "Incisal composite", tooth: "UL3", map: { I: { ...restored, material: "resin" } } },
    ...(["early", "arrested", "established"] as const).map((stage) => ({ label: `Caries · ${stage}`, tooth: "UR6", map: { O: { kind: "carious" as const, material: null, condition: `carious_${stage}` as const, defects: [] } } })),
    { label: "Caries · stage unspecified", tooth: "LL6", map: { O: newSurfaceObservation("carious") } },
    { label: "Defective gold", tooth: "LR6", map: { O: { ...restored, material: "gold", condition: "defective", defects: ["leaking"] } } },
    { label: "Fissure sealant", tooth: "LL6", map: { O: { kind: "sealant", material: null, condition: null, defects: [] } } },
  ];
  await page.setViewportSize({ width: 1360, height: 700 });
  await page.setContent(`<style>body{margin:24px;background:#f7f7f5;color:#242320;font:14px Arial}.gallery{display:flex;gap:10px}.tooth{background:white;border:1px solid #deded8;border-radius:10px;padding:12px 8px;flex:1;text-align:center}.tooth svg{width:110px;height:308px;margin:14px auto}.tooth strong{font-size:12px}.clinical-root-halo,.clinical-crown-halo,.clinical-surface-halo{opacity:0}body.dark{background:#171614;color:#f5f4f1}.dark .tooth{background:#211f1c;border-color:#3b3832}</style><h1>Current surface findings · synthetic schematic review</h1><p>Mesial points toward the arch centre. Upper palatal uses P; History remains unchanged.</p><div class="gallery">${examples.map(({ label, tooth, map }) => `<section class="tooth"><strong>${label}</strong>${markup(tooth, { ...currentProps(), surfaceObservations: map, selectedDiagnosticSurfaces: Object.keys(map) as SurfaceKey[] })}<span>${tooth}</span></section>`).join("")}</div>`);
  await page.screenshot({ path: testInfo.outputPath("surface-gallery-light.png"), fullPage: true });
  await page.evaluate(() => document.body.classList.add("dark"));
  await page.screenshot({ path: testInfo.outputPath("surface-gallery-dark.png"), fullPage: true });
});
