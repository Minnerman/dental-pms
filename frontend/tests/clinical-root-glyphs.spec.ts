import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { createElement, type ComponentProps } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { JsxEmit, ModuleKind, transpileModule } from "typescript";

import { getRootDrawingLandmarks, getToothAnatomy } from "../components/clinical/toothAnatomy";
import { rootAreaSummary, rootConditions, type RootCondition } from "../components/clinical/rootDiagnosis";

// Pure SVG regression tests: no server requests or patient fixtures. Reuse the
// real component rather than a duplicate drawing inside the test environment.
const componentFile = resolve(__dirname, "../components/clinical/OdontogramToothSvg.tsx");
const compiledComponent = transpileModule(readFileSync(componentFile, "utf8"), {
  compilerOptions: { module: ModuleKind.CommonJS, jsx: JsxEmit.ReactJSX },
}).outputText;
const componentModule = { exports: {} as typeof import("../components/clinical/OdontogramToothSvg") };
new Function("require", "module", "exports", compiledComponent)(
  createRequire(componentFile), componentModule, componentModule.exports
);
const { default: OdontogramToothSvg, getOdontogramToothType } = componentModule.exports;
const menuFile = resolve(__dirname, "../components/clinical/RootConditionMenu.tsx");
const menuModule = { exports: {} as typeof import("../components/clinical/RootConditionMenu") };
new Function("require", "module", "exports", transpileModule(readFileSync(menuFile, "utf8"), {
  compilerOptions: { module: ModuleKind.CommonJS, jsx: JsxEmit.ReactJSX },
}).outputText)(createRequire(menuFile), menuModule, menuModule.exports);
const { default: RootConditionMenu } = menuModule.exports;
type ToothProps = ComponentProps<typeof OdontogramToothSvg>;
const quadrants = ["UR", "UL", "LR", "LL"] as const;
const noAction = () => {};
let renderSequence = 0;

function toothMarkup(toothKey: string, props: Partial<ToothProps> = {}) {
  return renderToStaticMarkup(createElement(OdontogramToothSvg, {
    toothKey, toothType: getOdontogramToothType(toothKey), ...props,
  }), { identifierPrefix: `root-glyph-${renderSequence++}-` });
}

async function render(page: Page, toothKey: string, props: Partial<ToothProps> = {}) {
  await page.setContent(`<style>body{margin:30px}svg{width:100px;height:280px}.clinical-root-halo{opacity:0}</style>${toothMarkup(toothKey, props)}`);
  return page.getByTestId(`tooth-svg-${toothKey}`);
}

test("preserved partial root findings retain clipped colors without exposing individually numbered controls", async ({ page }) => {
  for (const quadrant of quadrants) {
    const tooth = `${quadrant}6`;
    for (const { value } of rootConditions) {
      await render(page, tooth, {
        rootConditions: { "2": { condition: value, apicectomy: false } }, onRootClick: noAction,
      });
      const target = page.getByTestId(`clinical-root-drawing-${tooth}-2`);
      await expect(target).toHaveAttribute("data-root-condition", value);
      await expect(target).toHaveAttribute("data-root-recorded", "true");
      await expect(target).not.toHaveAttribute("aria-label");
      await expect(page.getByTestId(`clinical-root-${tooth}`)).toHaveAttribute("aria-label", `${tooth} root area`);
      await expect(page.getByTestId(`clinical-root-${tooth}`)).toHaveAttribute("data-root-condition", "mixed");
      const finding = page.getByTestId(`clinical-root-finding-${tooth}-2`);
      await expect(finding).toHaveAttribute("data-condition", value);
      await expect(finding.locator(":scope > path")).toHaveAttribute("stroke", value.startsWith("post_core") ? "#c4a7ee" : "#ffd84d");
      await expect(finding.locator(":scope > path")).toHaveAttribute("d", getToothAnatomy(tooth).canals[1]);
      if (value.startsWith("post_core")) {
        await expect(finding.locator(":scope > path")).toHaveAttribute("stroke-dasharray", "62 200");
        const coverage = await finding.locator(":scope > path").evaluate((element) => {
          const path = element as SVGPathElement;
          const length = path.getTotalLength();
          return {
            shaft: path.isPointInStroke(path.getPointAtLength(length * .3)),
            apex: path.isPointInStroke(path.getPointAtLength(length)),
          };
        });
        expect(coverage).toEqual({ shaft: true, apex: false });
      }
      await expect(page.getByTestId(`clinical-root-defect-${tooth}-2`)).toHaveCount(value.endsWith("defective") ? 1 : 0);
      await expect(page.getByTestId(`clinical-root-finding-${tooth}-1`)).toHaveCount(0);
      await expect(page.getByTestId(`clinical-root-drawing-${tooth}-1`)).toHaveAttribute("data-root-condition", "unspecified");
      const clip = await finding.evaluate((element) => {
        const id = element.getAttribute("clip-path")!.slice(5, -1);
        return document.getElementById(id)!.querySelector("path")!.getAttribute("d");
      });
      expect(clip).toBe(getToothAnatomy(tooth).roots[1]);
      if (value.endsWith("defective")) {
        const pattern = await page.getByTestId(`clinical-root-defect-${tooth}-2`).locator("path").getAttribute("stroke");
        expect(pattern).toMatch(/^url\(#root-defect-/);
        await expect(page.locator("pattern path")).toHaveAttribute("stroke", "#b91c1c");
        await expect(page.locator("pattern path")).toHaveAttribute("d", /L.*L.*L/);
      }
    }
  }
});

test("preserved partial apicectomy drawings stay transverse in all quadrants and dentitions", async ({ page }) => {
  for (const quadrant of quadrants) {
    for (const dentition of ["permanent", "deciduous"] as const) {
      const tooth = `${quadrant}4`;
      const anatomy = getToothAnatomy(tooth, dentition);
      const chosen = anatomy.roots.length;
      const landmarks = getRootDrawingLandmarks(anatomy, chosen - 1);
      await render(page, tooth, {
        baselineCondition: { status: "present", dentition },
        rootConditions: { [chosen]: { condition: null, apicectomy: true } },
      });
      await expect(page.locator(`[data-testid^="clinical-root-apicectomy-${tooth}-"]`)).toHaveCount(1);
      const marker = page.getByTestId(`clinical-root-apicectomy-${tooth}-${chosen}`);
      await expect(marker.locator("path").last()).toHaveAttribute("d", `M${landmarks.apical.x - 7} ${landmarks.apical.y} H${landmarks.apical.x + 7}`);
      const geometry = await marker.locator("path").last().evaluate((element) => {
        const path = element as SVGPathElement;
        const a = path.getPointAtLength(0).matrixTransform(path.getScreenCTM()!);
        const b = path.getPointAtLength(path.getTotalLength()).matrixTransform(path.getScreenCTM()!);
        return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, yDifference: a.y - b.y };
      });
      const rootBox = await page.getByTestId(`tooth-root-${tooth}-${chosen}`).boundingBox();
      expect(Math.abs(geometry.yDifference)).toBeLessThan(0.001);
      expect(geometry.x).toBeGreaterThan(rootBox!.x - 3);
      expect(geometry.x).toBeLessThan(rootBox!.x + rootBox!.width + 3);
      if (quadrant[0] === "U") expect(geometry.y).toBeLessThan(rootBox!.y + rootBox!.height * .2);
      else expect(geometry.y).toBeGreaterThan(rootBox!.y + rootBox!.height * .8);
    }
  }
});

test("current roots are thicker without changing slots, crowns, surfaces or historical root geometry", async ({ page }) => {
  for (const quadrant of quadrants) {
    for (const dentition of ["permanent", "deciduous"] as const) {
      for (let position = 1; position <= (dentition === "permanent" ? 8 : 5); position++) {
        const tooth = `${quadrant}${position}`;
        const props = { baselineCondition: { status: "present" as const, dentition } };
        const anatomy = getToothAnatomy(tooth, dentition);
        await page.setContent(`<style>body{margin:0}.pair{display:flex}.pair svg{width:100px;height:280px}</style><div class="pair"><section id="history">${toothMarkup(tooth, props)}</section><section id="current">${toothMarkup(tooth, { ...props, rootConditions: {}, onRootClick: noAction })}</section></div>`);
        for (let root = 1; root <= anatomy.roots.length; root++) {
          const oldPath = page.locator("#history").getByTestId(`tooth-root-${tooth}-${root}`);
          const newPath = page.locator("#current").getByTestId(`tooth-root-${tooth}-${root}`);
          await expect(newPath).toHaveAttribute("d", anatomy.roots[root - 1]);
          const oldBox = (await oldPath.boundingBox())!;
          const newBox = (await newPath.boundingBox())!;
          expect(newBox.width / oldBox.width).toBeCloseTo(1.16, 3);
          expect(newBox.height).toBeCloseTo(oldBox.height, 4);
          expect(newBox.x).toBeGreaterThanOrEqual(100);
          expect(newBox.x + newBox.width).toBeLessThanOrEqual(200);
        }
        const now = page.locator("#current");
        const previous = page.locator("#history");
        await expect(now.locator('[data-testid^="clinical-root-"][role="button"]')).toHaveCount(1);
        await expect(now.getByTestId(`clinical-root-${tooth}`).locator(".clinical-root-halo")).toHaveCount(anatomy.roots.length);
        for (const part of [`tooth-crown-${tooth}`, `tooth-surface-map-${tooth}`]) {
          expect(await now.getByTestId(part).innerHTML()).toBe(await previous.getByTestId(part).innerHTML());
          const before = (await previous.getByTestId(part).boundingBox())!;
          const after = (await now.getByTestId(part).boundingBox())!;
          // Browser float matrices round translated SVG bounds by a few
          // millionths of a pixel; retain a much tighter than pixel tolerance.
          expect(after.width).toBeCloseTo(before.width, 3);
          expect(after.height).toBeCloseTo(before.height, 3);
          expect(after.y).toBeCloseTo(before.y, 3);
        }
        await expect(now.getByTestId(`tooth-svg-${tooth}`)).toHaveAttribute("viewBox", "0 0 100 280");
      }
    }
  }
});

test("neutral and explicit findings suppress conflicting legacy root symbols without altering History", async ({ page }) => {
  for (const quadrant of quadrants) {
    const tooth = `${quadrant}6`;
    const restorations: ToothProps["restorations"] = [{ type: "root_canal" }, { type: "post" }, { type: "crown" }];
    for (const condition of [null, "filled_sound"] as const) {
      await render(page, tooth, { restorations, rootConditions: { "1": { condition, apicectomy: false } } });
      await expect(page.getByTestId(`clinical-root-drawing-${tooth}-1`)).toHaveAttribute("data-root-recorded", "true");
      await expect(page.getByTestId(`clinical-root-finding-${tooth}-1`)).toHaveCount(condition ? 1 : 0);
      const historicalCanals = page.getByTestId(`tooth-anatomy-restoration-${tooth}-root_canal`).locator("path");
      await expect(historicalCanals).toHaveCount(getToothAnatomy(tooth).roots.length - 1);
      await expect(page.getByTestId(`tooth-anatomy-restoration-${tooth}-root_canal`).locator('[data-root-index="1"]')).toHaveCount(0);
      await expect(page.getByTestId(`tooth-anatomy-restoration-${tooth}-post`)).toHaveCount(0);
      await expect(page.getByTestId(`tooth-restoration-${tooth}-post`)).toHaveCount(0);
      await expect(page.getByTestId(`tooth-restoration-${tooth}-root_canal`)).toHaveCount(0);
      await expect(page.getByTestId(`tooth-anatomy-restoration-${tooth}-crown`)).toBeAttached();
    }
    await render(page, tooth, { restorations });
    await expect(page.getByTestId(`tooth-anatomy-restoration-${tooth}-root_canal`).locator("path")).toHaveCount(getToothAnatomy(tooth).roots.length);
    await expect(page.getByTestId(`tooth-anatomy-restoration-${tooth}-post`)).toBeAttached();
    await expect(page.getByTestId(`tooth-restoration-${tooth}-post`)).toBeAttached();
    await expect(page.getByTestId(`tooth-restoration-${tooth}-root_canal`)).toBeAttached();
  }
});

test("missing, implant, unerupted and untouched legacy absence never expose editable natural roots", async ({ page }) => {
  for (const quadrant of quadrants) {
    const tooth = `${quadrant}6`;
    for (const blocked of [
      { baselineCondition: { status: "missing" as const } },
      { baselineCondition: { status: "implant" as const } },
      { baselineCondition: { status: "unerupted" as const } },
      { missing: true }, { extracted: true },
      { restorations: [{ type: "implant" as const }] },
    ]) {
      const svg = await render(page, tooth, {
        ...blocked,
        rootConditions: blocked.baselineCondition ? { "1": { condition: "filled_defective", apicectomy: true } } : {},
        onRootClick: noAction, onRootContextMenu: noAction,
      });
      await expect(svg).toHaveAttribute("role", "img");
      await expect(svg.locator('[data-testid^="clinical-root-"][role="button"]')).toHaveCount(0);
      await expect(page.getByTestId(`clinical-root-finding-${tooth}-1`)).toHaveCount(0);
      await expect(page.getByTestId(`clinical-root-apicectomy-${tooth}-1`)).toHaveCount(0);
      if (blocked.baselineCondition?.status === "implant") {
        await expect(page.getByTestId(`tooth-baseline-implant-${tooth}`)).toBeAttached();
        await expect(page.locator(`[data-testid^="tooth-root-${tooth}-"]`)).toHaveCount(0);
      }
    }
    await render(page, tooth, {
      restorations: [{ type: "implant" }], baselineCondition: { status: "present" }, rootConditions: {}, onRootClick: noAction,
    });
    await expect(page.getByTestId(`clinical-root-${tooth}`)).toHaveAttribute("role", "button");
    await expect(page.getByTestId(`tooth-anatomy-restoration-${tooth}-implant`)).toHaveCount(0);
  }
});

test("saved native root observations take precedence over later legacy absence or implant without asserting tooth health", async ({ page }) => {
  for (const quadrant of quadrants) {
    const tooth = `${quadrant}6`;
    for (const condition of [null, "filled_defective"] as const) {
      const svg = await render(page, tooth, {
        missing: true, extracted: true,
        restorations: [{ type: "implant" }, { type: "extraction" }, { type: "filling", surfaces: ["M"] }, { type: "crown" }],
        rootConditions: { "1": { condition, apicectomy: condition !== null } }, onRootClick: noAction,
      });
      await expect(svg).not.toHaveAttribute("aria-label", /healthy|current condition present/);
      await expect(page.getByTestId(`clinical-root-drawing-${tooth}-1`)).toHaveAttribute("data-root-recorded", "true");
      await expect(page.getByTestId(`clinical-root-apicectomy-${tooth}-1`)).toHaveCount(condition ? 1 : 0);
      await expect(page.getByTestId(`clinical-root-finding-${tooth}-1`)).toHaveCount(condition ? 1 : 0);
      await expect(page.getByTestId(`tooth-anatomy-restoration-${tooth}-implant`)).toHaveCount(0);
      await expect(page.getByTestId(`tooth-restoration-${tooth}-implant`)).toHaveCount(0);
      await expect(page.getByTestId(`tooth-restoration-${tooth}-missing`)).toHaveCount(0);
      await expect(page.getByTestId(`tooth-restoration-${tooth}-extraction`)).toHaveCount(0);
      await expect(page.getByTestId(`tooth-anatomy-restoration-${tooth}-crown`)).toBeAttached();
      await expect(page.getByTestId(`tooth-restoration-${tooth}-filling-M`)).toBeAttached();
    }
  }
});

test("one root-area control uses British primary labels and preserves passive historical semantics", async ({ page }) => {
  for (const quadrant of quadrants) {
    const tooth = `${quadrant}5`;
    const svg = await render(page, tooth, {
      baselineCondition: { status: "present", dentition: "deciduous" },
      rootConditions: {}, onRootClick: noAction,
    });
    await expect(svg).toHaveAttribute("role", "group");
    const count = quadrant[0] === "U" ? 3 : 2;
    const control = page.getByTestId(`clinical-root-${tooth}`);
    await expect(control).toHaveAttribute("tabindex", "0");
    await expect(control).toHaveAttribute("aria-label", `${quadrant}E root area`);
    await expect(control.locator("title")).toHaveText(`${quadrant}E root area, current root finding unspecified`);
    await expect(control.locator(".clinical-root-halo")).toHaveCount(count);
    await expect(page.locator('[aria-label*="root 1"], [aria-label*="root 2"], [aria-label*="root 3"]')).toHaveCount(0);
    await expect(page.locator('[role="button"]')).toHaveCount(1);
    await render(page, tooth);
    await expect(page.getByTestId(`tooth-svg-${tooth}`)).toHaveAttribute("role", "img");
    await expect(page.locator("[tabindex], .clinical-root-halo")).toHaveCount(0);
  }
});

test("whole root area includes spaces between roots, excludes the crown, and keeps selection geometry fixed", async ({ page }) => {
  for (const quadrant of quadrants) {
    const tooth = `${quadrant}6`;
    const props = { rootConditions: {}, onRootClick: noAction, onRootContextMenu: noAction };
    await render(page, tooth, props);
    const control = page.getByTestId(`clinical-root-${tooth}`);
    const before = await control.boundingBox();
    const toothBefore = await page.getByTestId(`tooth-svg-${tooth}`).boundingBox();
    const hitResults = await page.getByTestId(`clinical-root-hit-${tooth}`).evaluate((element) => {
      const hit = element as SVGGraphicsElement;
      const matrix = hit.getScreenCTM()!;
      const actualTargets = [[25, 35], [61, 27], [50, 75], [50, 135]].map(([x, y]) => {
        const point = new DOMPoint(x, y).matrixTransform(matrix);
        return document.elementFromPoint(point.x, point.y)?.getAttribute("data-testid") ?? "";
      });
      return { actualTargets, id: hit.getAttribute("data-testid") };
    });
    expect(hitResults.actualTargets.slice(0, 3)).toEqual([hitResults.id, hitResults.id, hitResults.id]);
    expect(hitResults.actualTargets[3]).not.toBe(hitResults.id);
    await expect(control).toHaveAttribute("aria-pressed", "false");
    await expect(control.locator(".clinical-root-selection")).toHaveCount(0);
    await render(page, tooth, { ...props, rootSelected: true });
    const selected = page.getByTestId(`clinical-root-${tooth}`);
    await expect(selected).toHaveAttribute("aria-pressed", "true");
    await expect(selected).toHaveAttribute("data-root-selected", "true");
    await expect(selected.locator(".clinical-root-selection")).toHaveCount(getToothAnatomy(tooth).roots.length);
    expect(await selected.boundingBox()).toEqual(before);
    expect(await page.getByTestId(`tooth-svg-${tooth}`).boundingBox()).toEqual(toothBefore);
    const haloPaths = await selected.locator(".clinical-root-halo").evaluateAll((nodes) => nodes.map((node) => node.getAttribute("d")));
    expect(haloPaths).toEqual(getToothAnatomy(tooth).roots);
  }
});

test("whole-area batch observations render the same condition and apicectomy across every natural root", async ({ page }) => {
  for (const quadrant of quadrants) {
    for (const dentition of ["permanent", "deciduous"] as const) {
      const tooth = `${quadrant}${dentition === "permanent" ? 6 : 5}`;
      const anatomy = getToothAnatomy(tooth, dentition);
      for (const { value, label } of rootConditions) {
        await render(page, tooth, {
          baselineCondition: { status: "present", dentition },
          rootConditions: Object.fromEntries(anatomy.roots.map((_, index) => [index + 1, { condition: value, apicectomy: true }])),
          onRootClick: noAction, rootSelected: true,
        });
        const area = page.getByTestId(`clinical-root-${tooth}`);
        await expect(area).toHaveAttribute("data-root-condition", value);
        await expect(area).toHaveAttribute("data-apicectomy", "true");
        await expect(area.locator("title")).toContainText(`root area, ${label}, apicectomy recorded`);
        await expect(area.locator('[data-testid^="clinical-root-finding-"]')).toHaveCount(anatomy.roots.length);
        await expect(area.locator('[data-testid^="clinical-root-apicectomy-"]')).toHaveCount(anatomy.roots.length);
        await expect(area.locator('[data-testid^="clinical-root-defect-"]')).toHaveCount(value.endsWith("defective") ? anatomy.roots.length : 0);
        await expect(area.locator("[role], [tabindex], [aria-label]")).toHaveCount(0);
      }
    }
  }
});

test("root-area menu distinguishes partial prior findings from uniform whole-area observations", async ({ page }) => {
  const showMenu = async (current: ReturnType<typeof rootAreaSummary>) => {
    await page.setContent(renderToStaticMarkup(createElement(RootConditionMenu, {
      enabled: true, current, onChange: noAction,
    })));
  };
  for (const quadrant of quadrants) {
    for (const deciduous of [false, true]) {
      const tooth = `${quadrant}${deciduous ? 5 : 6}`;
      const anatomy = getToothAnatomy(tooth, deciduous ? "deciduous" : "permanent");
      const partial = rootAreaSummary(tooth, deciduous, {
        "1": { condition: "filled_sound", apicectomy: true },
      });
      expect(partial).toEqual({ condition: undefined, apicectomy: false, apicectomyMixed: true, mixed: true });
      await showMenu(partial);
      await expect(page.getByRole("menuitemcheckbox", { name: "Apicectomy" })).toHaveAttribute("aria-checked", "mixed");
      await expect(page.locator('[role="menuitemradio"][aria-checked="true"]')).toHaveCount(0);
      await expect(page.getByText("Existing root findings differ. Your choice will apply across this tooth’s root area.")).toBeVisible();

      for (const { value } of rootConditions) {
        const sameCondition = Object.fromEntries(anatomy.roots.map((_, index) => [index + 1, { condition: value, apicectomy: index === 0 }]));
        const partialApicectomy = rootAreaSummary(tooth, deciduous, sameCondition);
        expect(partialApicectomy).toEqual({ condition: value, apicectomy: false, apicectomyMixed: true, mixed: true });
        await showMenu(partialApicectomy);
        await expect(page.getByTestId(`clinical-root-condition-${value}`)).toHaveAttribute("aria-checked", "true");
        await expect(page.getByRole("menuitemcheckbox", { name: "Apicectomy" })).toHaveAttribute("aria-checked", "mixed");

        for (const apicectomy of [false, true]) {
          const uniform = rootAreaSummary(tooth, deciduous, Object.fromEntries(anatomy.roots.map((_, index) => [index + 1, { condition: value, apicectomy }])));
          expect(uniform).toEqual({ condition: value, apicectomy, apicectomyMixed: false, mixed: false });
          await showMenu(uniform);
          await expect(page.locator('[role="menuitemradio"][aria-checked="true"]')).toHaveCount(1);
          await expect(page.getByTestId(`clinical-root-condition-${value}`)).toHaveAttribute("aria-checked", "true");
          await expect(page.getByRole("menuitemcheckbox", { name: "Apicectomy" })).toHaveAttribute("aria-checked", String(apicectomy));
          await expect(page.getByText("Existing root findings differ. Your choice will apply across this tooth’s root area.")).toHaveCount(0);
        }
      }
      const neutral = rootAreaSummary(tooth, deciduous, Object.fromEntries(anatomy.roots.map((_, index) => [index + 1, { condition: null, apicectomy: false }])));
      expect(neutral).toEqual({ condition: null, apicectomy: false, apicectomyMixed: false, mixed: false });
      await showMenu(neutral);
      await expect(page.locator('[role="menuitemradio"][aria-checked="true"]')).toHaveCount(0);
      await expect(page.getByRole("menuitemcheckbox", { name: "Apicectomy" })).toHaveAttribute("aria-checked", "false");
    }
  }
});

test("synthetic root diagnosis gallery compares clear light and dark illustrations", async ({ page }, testInfo) => {
  const cases: Array<{ title: string; tooth: string; condition?: RootCondition; apicectomy?: boolean; primary?: boolean }> = [
    { title: "Unspecified", tooth: "UR6" },
    { title: "Filled sound", tooth: "UR6", condition: "filled_sound" },
    { title: "Filled defective", tooth: "UR6", condition: "filled_defective" },
    { title: "Post & core sound", tooth: "UR6", condition: "post_core_sound" },
    { title: "Post & core defective", tooth: "UR6", condition: "post_core_defective" },
    { title: "Apicectomy", tooth: "UR6", condition: "filled_sound", apicectomy: true },
    { title: "Lower apicectomy", tooth: "LL6", condition: "post_core_defective", apicectomy: true },
    { title: "Primary roots", tooth: "UR5", primary: true, condition: "filled_sound", apicectomy: true },
  ];
  await page.setViewportSize({ width: 1360, height: 650 });
  await page.setContent(`<style>body{margin:24px;background:#f7f7f5;color:#242320;font:14px Arial}.gallery{display:flex;gap:10px}.tooth{background:white;border:1px solid #deded8;border-radius:10px;padding:16px 9px;flex:1;text-align:center}.tooth svg{width:110px;height:308px;margin:12px auto}.tooth strong{font-size:12px}.clinical-root-halo{opacity:0}body.dark{background:#171614;color:#f5f4f1}.dark .tooth{background:#211f1c;border-color:#3b3832}</style><h1>Whole root-area observations · synthetic schematic review</h1><p>Yellow: root filling · Purple: post & core · Red crosshatching: defective · Transverse line: apicectomy</p><div class="gallery">${cases.map(({ title, tooth, condition, apicectomy, primary }) => `<section class="tooth"><strong>${title}</strong>${toothMarkup(tooth, { baselineCondition: { status: "present", dentition: primary ? "deciduous" : "permanent" }, rootConditions: condition || apicectomy ? Object.fromEntries(getToothAnatomy(tooth, primary ? "deciduous" : "permanent").roots.map((_, index) => [index + 1, { condition: condition ?? null, apicectomy: Boolean(apicectomy) }])) : {}, onRootClick: noAction })}<span>${primary ? "URE" : tooth}</span></section>`).join("")}</div>`);
  await page.screenshot({ path: testInfo.outputPath("root-diagnosis-gallery-light.png"), fullPage: true });
  await page.evaluate(() => document.body.classList.add("dark"));
  await page.screenshot({ path: testInfo.outputPath("root-diagnosis-gallery-dark.png"), fullPage: true });
});
