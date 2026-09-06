import { expect, test } from "@playwright/test";
import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { Children, createElement, isValidElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { JsxEmit, ModuleKind, ScriptTarget, transpileModule } from "typescript";
import { newSurfaceObservation, type SurfaceObservation } from "../components/clinical/surfaceDiagnosis";

// Compile actual component modules for server rendering; no patient or server access.
const cache = new Map<string, { exports: unknown }>();
function loadComponent<T>(name: string): T {
  const file = resolve(__dirname, `../components/clinical/${name}.tsx`);
  function load(filename: string): unknown {
    const cached = cache.get(filename);
    if (cached) return cached.exports;
    const compiledModule = { exports: {} };
    cache.set(filename, compiledModule);
    const require = createRequire(filename);
    const compiled = transpileModule(readFileSync(filename, "utf8"), {
      compilerOptions: { module: ModuleKind.CommonJS, jsx: JsxEmit.ReactJSX, target: ScriptTarget.ES2017 },
    }).outputText;
    new Function("require", "module", "exports", compiled)((specifier: string) => {
      const child = resolve(dirname(filename), `${specifier}.tsx`);
      return specifier.startsWith(".") && existsSync(child) ? load(child) : require(specifier);
    }, compiledModule, compiledModule.exports);
    return compiledModule.exports;
  }
  return load(file) as T;
}
const { default: Tabs } = loadComponent<typeof import("../components/clinical/DiagnosisLevelTabs")>("DiagnosisLevelTabs");
const { default: ToothPalette } = loadComponent<typeof import("../components/clinical/DiagnosisPalette")>("DiagnosisPalette");
const { default: RootPalette } = loadComponent<typeof import("../components/clinical/RootDiagnosisPalette")>("RootDiagnosisPalette");
const { default: CrownPalette } = loadComponent<typeof import("../components/clinical/CrownDiagnosisPalette")>("CrownDiagnosisPalette");
const { default: SurfacePalette } = loadComponent<typeof import("../components/clinical/SurfaceDiagnosisPalette")>("SurfaceDiagnosisPalette");
const { SurfaceKindChoices, SurfaceObservationControls } = loadComponent<typeof import("../components/clinical/SurfaceDiagnosisControls")>("SurfaceDiagnosisControls");
const noop = () => {};
type TestedProps = { "data-testid"?: string; children?: ReactNode; onClick?: () => void; onChange?: (event: { target: { value: string } }) => void };
function target(node: ReactNode, id: string): TestedProps | undefined {
  for (const child of Children.toArray(node)) {
    if (!isValidElement<TestedProps>(child)) continue;
    if (child.props["data-testid"] === id) return child.props;
    const nested = target(child.props.children, id);
    if (nested) return nested;
  }
}

test("new restored controls default Sound while existing null survives material edits and repeated category selection", async ({ page }) => {
  let changed: SurfaceObservation | undefined;
  const fresh = newSurfaceObservation("restored");
  expect(fresh.condition).toBe("sound");
  const onChange = (value: SurfaceObservation) => { changed = value; };
  const controls = (observation: SurfaceObservation) => SurfaceObservationControls({ observation, disabled: false, onChange, prefix: "test" });
  await page.setContent(renderToStaticMarkup(controls(fresh)));
  await expect(page.getByTestId("test-condition")).toHaveValue("sound");
  await expect(page.getByTestId("test-condition").locator('option[value=""]')).toHaveCount(0);
  const existing: SurfaceObservation = { kind: "restored", material: "gold", condition: null, defects: [] };
  const before = JSON.stringify(existing);
  await page.setContent(renderToStaticMarkup(controls(existing)));
  await expect(page.getByTestId("test-condition")).toHaveValue("");
  await expect(page.getByTestId("test-condition").locator('option[value=""]')).toHaveText("Not recorded (existing)");
  await expect(page.getByTestId("test-condition").locator('option[value=""]')).toHaveJSProperty("disabled", true);
  target(controls(existing), "test-material")!.onChange!({ target: { value: "amalgam" } });
  expect(changed).toEqual({ ...existing, material: "amalgam" });
  expect(JSON.stringify(existing)).toBe(before);
  const changedMaterial = changed!;
  target(SurfaceKindChoices({ observation: changedMaterial, disabled: false, onChange, prefix: "test" }), "test-restored")!.onClick!();
  expect(changed).toBe(changedMaterial);
  expect(changed!.condition).toBeNull();
  target(controls(changed!), "test-condition")!.onChange!({ target: { value: "sound" } });
  expect(changed).toEqual({ ...existing, material: "amalgam", condition: "sound" });
  for (const kind of ["carious", "sealant"] as const) {
    const observation = newSurfaceObservation(kind);
    expect(observation.condition).toBeNull();
    await page.setContent(renderToStaticMarkup(controls(observation)));
    await expect(page.getByTestId(kind === "carious" ? "test-stage" : "test-condition").locator('option[value=""]')).toHaveJSProperty("disabled", false);
  }
});

const palettes = {
  tooth: () => createElement(ToothPalette, { enabled: true, saving: false, action: "missing", selected: ["UR6"], lastAction: null, activeTooth: "UR6", onChoose: noop, onApply: noop, onCancel: noop, onArchMissing: noop, onNote: noop, onDetails: noop }),
  root: () => createElement(RootPalette, { enabled: true, saving: false, action: "apicectomy", selected: ["UR6"], onChoose: noop, onApply: noop, onCancel: noop, onBack: noop }),
  crown: () => createElement(CrownPalette, { enabled: true, saving: false, observation: { kind: "gold", issues: [] }, selected: ["UR6"], canNote: true, bridges: [], onChoose: noop, onApply: noop, onCancel: noop, onBack: noop, onNote: noop, onBridge: noop, onBridgeReset: noop }),
  surface: () => createElement(SurfacePalette, { disabled: false, observation: newSurfaceObservation("restored"), targets: [{ tooth: "UR6", surfaces: ["M", "O", "D"] }], onChange: noop, onApply: noop, onCancel: noop }),
};

test("one inline diagnosis header retains four accessible tabs while palettes omit redundant introductory blocks", async ({ page }) => {
  for (const level of ["tooth", "root", "crown", "surface"] as const) {
    await page.setContent(renderToStaticMarkup(createElement(Tabs, { value: level, disabled: false, onChange: noop })) + renderToStaticMarkup(palettes[level]()));
    await expect(page.getByText("Diagnosis:", { exact: true })).toHaveCount(1);
    await expect(page.getByRole("tablist", { name: "Diagnosis level" })).toBeVisible();
    await expect(page.getByRole("tab")).toHaveCount(4);
    for (const label of ["Tooth level", "Root level", "Crown level", "Surface level"]) {
      await expect(page.getByRole("tab", { name: label, exact: true })).toHaveText(label);
    }
    await expect(page.getByTestId(`diagnosis-level-${level}`)).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId(`diagnosis-level-${level}`)).toHaveAttribute("tabindex", "0");
    await expect(page.locator('.clinical-diagnosis-heading, .clinical-diagnosis-palette > p')).toHaveCount(0);
    await expect(page.locator('[data-testid="root-diagnosis-back"], [data-testid="crown-diagnosis-back"]')).toHaveCount(0);
    await expect(page.locator('.clinical-diagnosis-selection')).toContainText("UR6");
    await expect(page.getByRole("button", { name: /Apply to/ })).toBeEnabled();
  }
  await page.setContent(renderToStaticMarkup(createElement(Tabs, { value: "surface", disabled: true, onChange: noop })));
  for (const level of ["tooth", "root", "crown", "surface"]) await expect(page.getByTestId(`diagnosis-level-${level}`)).toBeDisabled();
});

test("actual compact level styles use one desktop row and wrap legibly on mobile in both themes", async ({ page }, testInfo) => {
  const stylesheet = readFileSync(resolve(__dirname, "../app/(app)/patients/[id]/patient-responsive.module.css"), "utf8");
  const rowCss = stylesheet.slice(stylesheet.indexOf('.shell :global(.clinical-diagnosis-workspace)'), stylesheet.indexOf('.shell :global(.clinical-baseline-feedback)')).replace(/:global\(([^)]+)\)/g, "$1");
  for (const width of [1100, 390]) {
    await page.setViewportSize({ width, height: 220 });
    await page.setContent(`<style>body{margin:16px;font:14px Arial;--panel:#fff;--text:#25241f;--border:#dedbd4;--accent:#00bcea;background:#f7f7f5;color:var(--text)}body.dark{--panel:#211f1c;--text:#f5f2ed;--border:#484138;background:#171614}${rowCss}</style><main class="shell">${renderToStaticMarkup(createElement(Tabs, { value: "surface", disabled: false, onChange: noop }))}<p>Synthetic layout review</p></main>`);
    const boxes = await page.getByRole("tab").evaluateAll((elements) => elements.map((element) => { const box = element.getBoundingClientRect(); return { x: box.x, y: box.y, right: box.right }; }));
    expect(new Set(boxes.map(({ y }) => y)).size).toBe(width > 540 ? 1 : 2);
    for (const box of boxes) { expect(box.x).toBeGreaterThanOrEqual(0); expect(box.right).toBeLessThanOrEqual(width); }
    expect((await page.getByTestId("clinical-diagnosis-levels").boundingBox())!.height).toBeLessThanOrEqual(width > 540 ? 48 : 104);
    await page.screenshot({ path: testInfo.outputPath(`diagnosis-inline-${width}-light.png`) });
    await page.evaluate(() => document.body.classList.add("dark"));
    await page.screenshot({ path: testInfo.outputPath(`diagnosis-inline-${width}-dark.png`) });
  }
});
